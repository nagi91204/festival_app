from datetime import timedelta
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.db import IntegrityError, transaction
from django.db.models import F, Max
from django.utils import timezone

from .models import BuzzerAttempt, Game, GamePlayer, GameQuestion, PlayerAnswer, Question, RankingEntry


class QuizConsumer(AsyncJsonWebsocketConsumer):
    """ゲームごとの全画面を接続し、DBを正しい状態の唯一の基準にする。"""

    async def connect(self):
        self.game_id = self.scope["url_route"]["kwargs"]["game_id"]
        self.group_name = f"quiz_{self.game_id}"
        self.player_id = None
        if not await self.game_exists():
            await self.close(code=4404)
            return
        requested_admin = self.scope["path"].rstrip("/").endswith("/admin")
        query = parse_qs(self.scope.get("query_string", b"").decode())
        self.is_admin = requested_admin and await self.valid_admin_token(query.get("key", [""])[0])
        if requested_admin and not self.is_admin:
            await self.close(code=4403)
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_state()

    async def disconnect(self, close_code):
        if self.player_id:
            await self.set_connected(self.player_id, False)
            await self.broadcast_state()
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        action = content.get("action")
        try:
            admin_actions = {
                "start_next_question", "close_answers", "reveal_result", "open_buzzer",
                "judge_buzzer", "adjust_score", "set_seconds", "expire_question", "play_audio",
            }
            if action in admin_actions and not self.is_admin:
                raise ValueError("管理者画面から操作してください。")
            if action == "request_state":
                await self.send_state()
                return
            if action == "join_player":
                player = await self.join_player(content.get("nickname", ""), content.get("player_id"))
                self.player_id = str(player["id"])
                await self.send_json({"type": "joined", "player_id": self.player_id, "nickname": player["nickname"]})
                await self.broadcast_state()
                return
            if action == "submit_answer":
                await self.submit_answer(int(content.get("choice")))
            elif action == "buzz":
                await self.buzz()
            elif action == "start_next_question":
                await self.start_next_question()
            elif action == "close_answers":
                await self.close_answers()
            elif action == "reveal_result":
                await self.reveal_result()
            elif action == "open_buzzer":
                await self.open_buzzer()
            elif action == "judge_buzzer":
                # JSONの boolean 以外を正解扱いにしない。
                if not isinstance(content.get("correct"), bool):
                    raise ValueError("正誤の値が正しくありません。")
                await self.judge_buzzer(content["correct"])
            elif action == "adjust_score":
                await self.adjust_score(content.get("player_id"), int(content.get("delta")))
            elif action == "set_seconds":
                await self.set_seconds(int(content.get("seconds")))
            elif action == "expire_question":
                await self.expire_question()
            elif action == "play_audio":
                await self.channel_layer.group_send(self.group_name, {"type": "audio.play"})
                return
            else:
                raise ValueError("不明な操作です。")
            await self.broadcast_state()
        except (Game.DoesNotExist, GameQuestion.DoesNotExist, GamePlayer.DoesNotExist, ValueError, TypeError, IntegrityError) as error:
            await self.send_json({"type": "error", "message": str(error) or "操作できません。"})

    async def state_update(self, event):
        await self.send_state()

    async def audio_play(self, event):
        await self.send_json({"type": "play_audio"})

    async def broadcast_state(self):
        await self.channel_layer.group_send(self.group_name, {"type": "state.update"})

    async def send_state(self):
        await self.send_json({"type": "state", "state": await self.get_state(self.is_admin)})

    @database_sync_to_async
    def game_exists(self):
        return Game.objects.filter(id=self.game_id).exists()

    @database_sync_to_async
    def valid_admin_token(self, token):
        return Game.objects.filter(id=self.game_id, admin_token=token).exists()

    @database_sync_to_async
    def set_connected(self, player_id, connected):
        GamePlayer.objects.filter(id=player_id, game_id=self.game_id).update(connected=connected)

    @database_sync_to_async
    def join_player(self, raw_nickname, old_player_id):
        nickname = str(raw_nickname).strip()[:20]
        if not nickname:
            raise ValueError("ニックネームを入力してください。")
        with transaction.atomic():
            game = Game.objects.select_for_update().get(id=self.game_id)
            if game.status == Game.Status.FINISHED:
                raise ValueError("このゲームは終了しています。")
            if old_player_id:
                player = GamePlayer.objects.filter(id=old_player_id, game=game).first()
                if player:
                    player.connected = True
                    player.save(update_fields=["connected"])
                    return {"id": player.id, "nickname": player.nickname}
            if game.players.count() >= game.max_players:
                raise ValueError(f"参加者は最大{game.max_players}人です。")
            if game.players.filter(nickname=nickname).exists():
                raise ValueError("そのニックネームはすでに使われています。")
            used_slots = set(game.players.values_list("slot", flat=True))
            slot = next(number for number in range(1, game.max_players + 1) if number not in used_slots)
            player = GamePlayer.objects.create(game=game, nickname=nickname, slot=slot)
            return {"id": player.id, "nickname": player.nickname}

    @database_sync_to_async
    def submit_answer(self, choice):
        if not self.player_id:
            raise ValueError("先に参加してください。")
        with transaction.atomic():
            game, game_question = self.lock_current_game_question()
            if self.expire_if_needed(game):
                raise ValueError("回答時間が終了しました。")
            if game.phase != Game.Phase.QUESTION or game_question.question.question_type != Question.QuestionType.CHOICE:
                raise ValueError("現在は選択式の回答時間ではありません。")
            if choice not in range(1, len(game_question.question.choices) + 1):
                raise ValueError("選択肢が正しくありません。")
            player = GamePlayer.objects.select_for_update().get(id=self.player_id, game=game)
            if PlayerAnswer.objects.filter(game_question=game_question, player=player).exists():
                raise ValueError("この問題にはすでに回答済みです。")
            correct = choice == game_question.question.correct_choice
            PlayerAnswer.objects.create(game_question=game_question, player=player, selected_choice=choice, is_correct=correct)
            if correct:
                GamePlayer.objects.filter(id=player.id).update(score=F("score") + game_question.question.points)

    @database_sync_to_async
    def buzz(self):
        if not self.player_id:
            raise ValueError("先に参加してください。")
        with transaction.atomic():
            game, game_question = self.lock_current_game_question()
            if self.expire_if_needed(game):
                raise ValueError("早押し受付時間が終了しました。")
            if game.phase != Game.Phase.BUZZER_OPEN:
                raise ValueError("現在は早押しを受け付けていません。")
            player = GamePlayer.objects.get(id=self.player_id, game=game)
            if BuzzerAttempt.objects.filter(game_question=game_question, player=player).exists():
                raise ValueError("この問題ではすでに早押し済みです。")
            BuzzerAttempt.objects.create(game_question=game_question, player=player)
            game.buzzed_player = player
            game.phase = Game.Phase.BUZZER_LOCKED
            game.save(update_fields=["buzzed_player", "phase"])

    @database_sync_to_async
    def start_next_question(self):
        with transaction.atomic():
            game = Game.objects.select_for_update().get(id=self.game_id)
            if game.status == Game.Status.FINISHED:
                raise ValueError("このゲームは終了しています。")
            if game.status == Game.Status.LOBBY:
                self.create_random_questions(game)
                game.status = Game.Status.RUNNING
            next_index = game.current_index + 1
            if not GameQuestion.objects.filter(game=game, position=next_index).exists():
                self.finish_game(game)
                return
            question = GameQuestion.objects.select_related("question").get(game=game, position=next_index).question
            game.current_index = next_index
            game.buzzed_player = None
            game.question_started_at = timezone.now()
            game.phase = Game.Phase.QUESTION if question.question_type == Question.QuestionType.CHOICE else Game.Phase.BUZZER_OPEN
            game.save(update_fields=["status", "current_index", "buzzed_player", "question_started_at", "phase"])

    @database_sync_to_async
    def close_answers(self):
        # select_for_update() はトランザクション内でのみ有効。
        with transaction.atomic():
            game, _ = self.lock_current_game_question()
            if game.phase != Game.Phase.QUESTION:
                raise ValueError("選択式の回答時間ではありません。")
            game.phase = Game.Phase.ANSWER_CLOSED
            game.save(update_fields=["phase"])

    @database_sync_to_async
    def reveal_result(self):
        with transaction.atomic():
            game, _ = self.lock_current_game_question()
            if game.phase not in (Game.Phase.QUESTION, Game.Phase.ANSWER_CLOSED, Game.Phase.BUZZER_LOCKED):
                raise ValueError("現在は結果を発表できません。")
            game.phase = Game.Phase.RESULT
            game.save(update_fields=["phase"])

    @database_sync_to_async
    def open_buzzer(self):
        with transaction.atomic():
            game, game_question = self.lock_current_game_question()
            if game_question.question.question_type not in (Question.QuestionType.BUZZER, Question.QuestionType.AUDIO):
                raise ValueError("早押し問題ではありません。")
            game.buzzed_player = None
            game.phase = Game.Phase.BUZZER_OPEN
            game.save(update_fields=["buzzed_player", "phase"])

    @database_sync_to_async
    def judge_buzzer(self, correct):
        with transaction.atomic():
            game, game_question = self.lock_current_game_question()
            if game.phase != Game.Phase.BUZZER_LOCKED or not game.buzzed_player_id:
                raise ValueError("判定する早押し回答者がいません。")
            attempt = BuzzerAttempt.objects.select_for_update().get(game_question=game_question, player=game.buzzed_player)
            delta = game_question.question.points if correct else 0
            attempt.is_correct = correct
            attempt.score_delta = delta
            attempt.save(update_fields=["is_correct", "score_delta"])
            if delta:
                GamePlayer.objects.filter(id=game.buzzed_player_id).update(score=F("score") + delta)
            game.buzzed_player = None
            game.phase = Game.Phase.RESULT if correct else Game.Phase.BUZZER_OPEN
            game.save(update_fields=["buzzed_player", "phase"])

    @database_sync_to_async
    def adjust_score(self, player_id, delta):
        delta = max(-100, min(delta, 100))
        if not player_id:
            raise ValueError("参加者を選んでください。")
        updated = GamePlayer.objects.filter(id=player_id, game_id=self.game_id).update(score=F("score") + delta)
        if not updated:
            raise ValueError("参加者が見つかりません。")

    @database_sync_to_async
    def set_seconds(self, seconds):
        seconds = max(5, min(seconds, 120))
        Game.objects.filter(id=self.game_id, status=Game.Status.LOBBY).update(seconds_per_question=seconds)

    @database_sync_to_async
    def expire_question(self):
        """期限を過ぎた問題だけを締め切る。複数画面からの同時要求にも耐える。"""
        with transaction.atomic():
            game = Game.objects.select_for_update().get(id=self.game_id)
            self.expire_if_needed(game)

    def expire_if_needed(self, game):
        if not game.question_started_at or timezone.now() < game.question_started_at + timedelta(seconds=game.seconds_per_question):
            return False
        if game.phase == Game.Phase.QUESTION:
            game.phase = Game.Phase.ANSWER_CLOSED
        elif game.phase in (Game.Phase.BUZZER_OPEN, Game.Phase.BUZZER_LOCKED):
            game.phase = Game.Phase.RESULT
            game.buzzed_player = None
        else:
            return False
        game.save(update_fields=["phase", "buzzed_player"])
        return True

    def lock_current_game_question(self):
        game = Game.objects.select_for_update().select_related("buzzed_player").get(id=self.game_id)
        game_question = GameQuestion.objects.select_related("question").get(game=game, position=game.current_index)
        return game, game_question

    def create_random_questions(self, game):
        if game.game_questions.exists():
            return
        candidates = list(Question.objects.filter(is_active=True).order_by("?")[: game.question_count])
        if not candidates:
            raise ValueError("Adminで有効な問題を1問以上登録してください。")
        GameQuestion.objects.bulk_create([GameQuestion(game=game, question=question, position=index) for index, question in enumerate(candidates)])

    def finish_game(self, game):
        game.status = Game.Status.FINISHED
        game.phase = Game.Phase.FINISHED
        game.buzzed_player = None
        game.save(update_fields=["status", "phase", "buzzed_player"])
        RankingEntry.objects.filter(game=game).delete()
        players = list(game.players.order_by("-score", "joined_at"))
        rankings, previous_score, previous_rank = [], None, 0
        for position, player in enumerate(players, start=1):
            rank = previous_rank if player.score == previous_score else position
            rankings.append(RankingEntry(game=game, player_name=player.nickname, score=player.score, rank=rank))
            previous_score, previous_rank = player.score, rank
        RankingEntry.objects.bulk_create(rankings)

    @database_sync_to_async
    def get_state(self, include_admin=False):
        game = Game.objects.select_related("buzzed_player").get(id=self.game_id)
        players = list(game.players.order_by("-score", "slot"))
        game_questions = list(GameQuestion.objects.filter(game=game).select_related("question").order_by("position"))
        current_gq = next((item for item in game_questions if item.position == game.current_index), None)
        question_data, answer_data = None, []
        if current_gq:
            question = current_gq.question
            question_data = {"number": game.current_index + 1, "total": len(game_questions), "type": question.question_type, "category": question.category, "body": question.body, "choices": question.choices, "points": question.points, "image_url": question.image.url if question.image else "", "audio_url": question.audio_file.url if question.audio_file else ""}
            if include_admin or game.phase in (Game.Phase.RESULT, Game.Phase.FINISHED):
                question_data.update({"correct_choice": question.correct_choice, "correct_text": question.correct_text or (question.choices[question.correct_choice - 1] if question.correct_choice else ""), "explanation": question.explanation})
                answer_data = list(current_gq.answers.select_related("player").values("player__nickname", "selected_choice", "is_correct"))
        answered_ids = list(current_gq.answers.values_list("player_id", flat=True)) if current_gq else []
        rankings = list(game.ranking_entries.values("rank", "player_name", "score"))
        previous_best = RankingEntry.objects.exclude(game=game).aggregate(best=Max("score"))["best"]
        current_best = rankings[0]["score"] if rankings else None
        buzzer_attempts = []
        if include_admin and current_gq:
            buzzer_attempts = list(current_gq.buzz_attempts.select_related("player").values("player__nickname", "is_correct", "score_delta", "buzzed_at"))
        return {"game": {"id": str(game.id), "title": game.title, "status": game.status, "phase": game.phase, "seconds": game.seconds_per_question, "deadline": (game.question_started_at + timedelta(seconds=game.seconds_per_question)).isoformat() if game.question_started_at else None, "buzzed_player_id": str(game.buzzed_player_id) if game.buzzed_player_id else None}, "question": question_data, "players": [{"id": str(p.id), "nickname": p.nickname, "slot": p.slot, "score": p.score, "connected": p.connected, "answered": str(p.id) in {str(answered) for answered in answered_ids}} for p in players], "answers": answer_data, "buzzer_attempts": buzzer_attempts, "rankings": rankings, "is_new_record": current_best is not None and (previous_best is None or current_best > previous_best)}
