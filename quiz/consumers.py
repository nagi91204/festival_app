from datetime import timedelta
import random
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.db import IntegrityError, transaction
from django.db.models import F, Max
from django.utils import timezone

from .models import BuzzerAttempt, Game, GameLog, GamePlayer, GameQuestion, PlayerAnswer, Question, RankingEntry


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
                "start_next_question", "advance_game", "close_answers", "reveal_result", "open_buzzer",
                "judge_buzzer", "adjust_score", "set_seconds", "set_game_minutes", "expire_question", "play_audio", "finish_game", "reset_game",
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
            elif action == "advance_game":
                await self.advance_game()
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
            elif action == "set_game_minutes":
                await self.set_game_minutes(int(content.get("minutes")))
            elif action == "expire_question":
                await self.expire_question()
            elif action == "tick":
                await self.tick()
            elif action == "play_audio":
                await self.validate_audio_playback()
                await self.channel_layer.group_send(self.group_name, {"type": "audio.play"})
                return
            elif action == "finish_game":
                await self.end_game()
            elif action == "reset_game":
                await self.reset_game()
                await self.channel_layer.group_send(self.group_name, {"type": "game.reset"})
            else:
                raise ValueError("不明な操作です。")
            await self.broadcast_state()
        except (Game.DoesNotExist, GameQuestion.DoesNotExist, GamePlayer.DoesNotExist, ValueError, TypeError, IntegrityError) as error:
            await self.send_json({"type": "error", "message": str(error) or "操作できません。"})

    async def state_update(self, event):
        await self.send_state()

    async def audio_play(self, event):
        await self.send_json({"type": "play_audio"})

    async def game_reset(self, event):
        await self.send_json({"type": "game_reset"})

    async def broadcast_state(self):
        await self.channel_layer.group_send(self.group_name, {"type": "state.update"})

    async def send_state(self):
        await self.send_json({"type": "state", "state": await self.get_state(self.is_admin, self.player_id)})

    @database_sync_to_async
    def game_exists(self):
        return Game.objects.filter(id=self.game_id).exists()

    @database_sync_to_async
    def valid_admin_token(self, token):
        return Game.objects.filter(id=self.game_id, admin_token=token).exists()

    @database_sync_to_async
    def set_connected(self, player_id, connected):
        with transaction.atomic():
            player = GamePlayer.objects.select_for_update().select_related("game").filter(id=player_id, game_id=self.game_id).first()
            if player and player.connected != connected:
                player.connected = connected
                player.save(update_fields=["connected"])
                self.add_log(player.game, "disconnected" if not connected else "connected", f"{player.nickname} さんが{'退出' if not connected else '再接続'}しました。", player)
                if not connected:
                    game = Game.objects.select_for_update().get(id=player.game_id)
                    game_question = GameQuestion.objects.select_related("question").filter(game=game, position=game.current_index).first()
                    if game_question:
                        self.start_auto_result_if_all_answered(game, game_question)

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
                    self.add_log(game, "rejoined", f"{player.nickname} さんが再接続しました。", player)
                    game_question = GameQuestion.objects.select_related("question").filter(game=game, position=game.current_index).first()
                    if game_question:
                        self.start_auto_result_if_all_answered(game, game_question)
                    return {"id": player.id, "nickname": player.nickname}
            if game.players.count() >= game.max_players:
                raise ValueError(f"参加者は最大{game.max_players}人です。")
            if game.players.filter(nickname=nickname).exists():
                raise ValueError("そのニックネームはすでに使われています。")
            used_slots = set(game.players.values_list("slot", flat=True))
            slot = next(number for number in range(1, game.max_players + 1) if number not in used_slots)
            player = GamePlayer.objects.create(game=game, nickname=nickname, slot=slot)
            self.add_log(game, "joined", f"{player.nickname} さんが参加しました。", player)
            return {"id": player.id, "nickname": player.nickname}

    @database_sync_to_async
    def submit_answer(self, choice):
        if not self.player_id:
            raise ValueError("先に参加してください。")
        with transaction.atomic():
            game, game_question = self.lock_current_game_question()
            if self.expire_if_needed(game):
                raise ValueError("回答時間が終了しました。")
            if game.phase != Game.Phase.QUESTION or game_question.question.question_type not in (Question.QuestionType.CHOICE, Question.QuestionType.IMAGE):
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
            self.add_log(game, "answer", f"{player.nickname} さんが問題 {game.current_index + 1} に {choice}番で回答（{'正解' if correct else '不正解'}）。", player)
            self.start_auto_result_if_all_answered(game, game_question)

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
            self.add_log(game, "buzz", f"{player.nickname} さんが問題 {game.current_index + 1} で早押ししました。", player)

    @database_sync_to_async
    def start_next_question(self):
        with transaction.atomic():
            game = Game.objects.select_for_update().get(id=self.game_id)
            self.start_next_question_locked(game)

    @database_sync_to_async
    def end_game(self):
        with transaction.atomic():
            game = Game.objects.select_for_update().get(id=self.game_id)
            if game.status != Game.Status.FINISHED:
                self.finish_game(game)

    @database_sync_to_async
    def reset_game(self):
        with transaction.atomic():
            game = Game.objects.select_for_update().get(id=self.game_id)
            if game.status != Game.Status.FINISHED:
                raise ValueError("ゲーム終了後にリセットできます。")
            game.logs.all().delete()
            game.players.all().delete()
            game.game_questions.all().delete()
            game.round_number += 1
            game.status = Game.Status.LOBBY
            game.phase = Game.Phase.LOBBY
            game.current_index = -1
            game.question_started_at = None
            game.game_started_at = None
            game.question_open_at = None
            game.result_advance_at = None
            game.buzzed_player = None
            game.save(update_fields=["status", "phase", "current_index", "question_started_at", "game_started_at", "question_open_at", "result_advance_at", "buzzed_player", "round_number"])
            self.add_log(game, "game_reset", "次のゲームのためにリセットしました。")

    @database_sync_to_async
    def advance_game(self):
        """司会用の主ボタン。状態に応じて紹介・答え合わせ・次問へ進める。"""
        with transaction.atomic():
            game = Game.objects.select_for_update().get(id=self.game_id)
            if game.status == Game.Status.FINISHED:
                raise ValueError("このゲームは終了しています。")
            if game.phase in (Game.Phase.LOBBY, Game.Phase.RESULT):
                self.start_next_question_locked(game)
            elif game.phase == Game.Phase.INTRO:
                self.open_current_question(game)
            elif game.phase in (Game.Phase.QUESTION, Game.Phase.ANSWER_CLOSED, Game.Phase.BUZZER_OPEN, Game.Phase.BUZZER_LOCKED):
                game.phase = Game.Phase.RESULT
                game.save(update_fields=["phase"])
                self.add_log(game, "result_revealed", f"問題 {game.current_index + 1} の結果を発表しました。")
            else:
                raise ValueError("現在は次へ進めません。")

    def start_next_question_locked(self, game):
        if game.status == Game.Status.FINISHED:
            raise ValueError("このゲームは終了しています。")
        # 制限時間後は現在の問題を最後として扱い、次の問題へは進めない。
        if game.game_started_at and game.status == Game.Status.RUNNING and timezone.now() >= game.game_started_at + timedelta(seconds=game.total_seconds):
            self.finish_game(game)
            return
        if game.status == Game.Status.LOBBY:
            self.create_random_questions(game)
            game.status = Game.Status.RUNNING
            game.game_started_at = timezone.now()
        next_index = game.current_index + 1
        if not GameQuestion.objects.filter(game=game, position=next_index).exists():
            self.finish_game(game)
            return
        question = GameQuestion.objects.select_related("question").get(game=game, position=next_index).question
        game.current_index = next_index
        game.buzzed_player = None
        game.question_started_at = None
        game.question_open_at = timezone.now() + timedelta(seconds=3)
        game.result_advance_at = None
        game.phase = Game.Phase.INTRO
        game.save(update_fields=["status", "game_started_at", "current_index", "buzzed_player", "question_started_at", "question_open_at", "result_advance_at", "phase"])
        self.add_log(game, "question_intro", f"次は問題 {next_index + 1}（{question.get_question_type_display()}）です。")

    def open_current_question(self, game):
        game_question = GameQuestion.objects.select_related("question").get(game=game, position=game.current_index)
        question = game_question.question
        game.question_started_at = timezone.now()
        game.question_open_at = None
        game.phase = Game.Phase.QUESTION if question.question_type in (Question.QuestionType.CHOICE, Question.QuestionType.IMAGE) else Game.Phase.BUZZER_OPEN
        game.save(update_fields=["question_started_at", "question_open_at", "phase"])
        self.add_log(game, "question_started", f"問題 {game.current_index + 1}「{question.title}」を開始しました。")

    def open_current_question_if_ready(self, game):
        if game.phase == Game.Phase.INTRO and game.question_open_at and timezone.now() >= game.question_open_at:
            self.open_current_question(game)
            return True
        return False

    def advance_after_result_if_ready(self, game):
        if game.phase == Game.Phase.RESULT and game.result_advance_at and timezone.now() >= game.result_advance_at:
            self.add_log(game, "next_question_auto", f"問題 {game.current_index + 1} の正解発表を終了し、自動で次の問題へ進みます。")
            self.start_next_question_locked(game)
            return True
        return False

    def start_auto_result_if_all_answered(self, game, game_question):
        if game.phase != Game.Phase.QUESTION or game_question.question.question_type not in (Question.QuestionType.CHOICE, Question.QuestionType.IMAGE):
            return False
        eligible_count = game.players.filter(connected=True).count()
        if not eligible_count or game_question.answers.count() < eligible_count:
            return False
        game.phase = Game.Phase.RESULT
        game.result_advance_at = timezone.now() + timedelta(seconds=4)
        game.save(update_fields=["phase", "result_advance_at"])
        self.add_log(game, "all_answered", f"全員が問題 {game.current_index + 1} に回答したため、自動で正解発表に進み、4秒後に次の問題へ進みます。")
        return True

    @database_sync_to_async
    def close_answers(self):
        # select_for_update() はトランザクション内でのみ有効。
        with transaction.atomic():
            game, _ = self.lock_current_game_question()
            if game.phase != Game.Phase.QUESTION:
                raise ValueError("選択式の回答時間ではありません。")
            game.phase = Game.Phase.ANSWER_CLOSED
            game.save(update_fields=["phase"])
            self.add_log(game, "answers_closed", f"問題 {game.current_index + 1} の回答を締め切りました。")

    @database_sync_to_async
    def reveal_result(self):
        with transaction.atomic():
            game, _ = self.lock_current_game_question()
            if game.phase not in (Game.Phase.QUESTION, Game.Phase.ANSWER_CLOSED, Game.Phase.BUZZER_LOCKED):
                raise ValueError("現在は結果を発表できません。")
            game.phase = Game.Phase.RESULT
            game.result_advance_at = None
            game.save(update_fields=["phase", "result_advance_at"])
            self.add_log(game, "result_revealed", f"問題 {game.current_index + 1} の結果を発表しました。")

    @database_sync_to_async
    def open_buzzer(self):
        with transaction.atomic():
            game, game_question = self.lock_current_game_question()
            if game_question.question.question_type not in (Question.QuestionType.BUZZER, Question.QuestionType.AUDIO):
                raise ValueError("早押し問題ではありません。")
            if game.phase not in (Game.Phase.BUZZER_OPEN, Game.Phase.BUZZER_LOCKED):
                raise ValueError("現在は早押しを開けません。")
            game.buzzed_player = None
            game.phase = Game.Phase.BUZZER_OPEN
            game.save(update_fields=["buzzed_player", "phase"])
            self.add_log(game, "buzzer_opened", f"問題 {game.current_index + 1} の早押しを開きました。")

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
            self.add_log(game, "buzz_judged", f"{attempt.player.nickname} さんの早押しを{'正解' if correct else '不正解'}と判定しました。", attempt.player)

    @database_sync_to_async
    def adjust_score(self, player_id, delta):
        delta = max(-100, min(delta, 100))
        if not player_id:
            raise ValueError("参加者を選んでください。")
        player = GamePlayer.objects.filter(id=player_id, game_id=self.game_id).first()
        if not player:
            raise ValueError("参加者が見つかりません。")
        if player.game.status == Game.Status.FINISHED:
            raise ValueError("終了したゲームの得点は変更できません。")
        GamePlayer.objects.filter(id=player.id).update(score=F("score") + delta)
        self.add_log(player.game, "score_adjusted", f"{player.nickname} さんの得点を {delta:+d} 点に調整しました。", player)

    @database_sync_to_async
    def set_seconds(self, seconds):
        seconds = max(5, min(seconds, 3600))
        game = Game.objects.filter(id=self.game_id, status=Game.Status.LOBBY).first()
        if game:
            game.seconds_per_question = seconds  # 旧データとの互換用
            game.total_seconds = seconds
            game.save(update_fields=["seconds_per_question", "total_seconds"])
            self.add_log(game, "seconds_changed", f"ゲーム時間を {seconds // 60 if seconds >= 60 else 1} 分に変更しました。")

    @database_sync_to_async
    def set_game_minutes(self, minutes):
        minutes = max(1, min(minutes, 120))
        game = Game.objects.filter(id=self.game_id, status=Game.Status.LOBBY).first()
        if game:
            game.total_seconds = minutes * 60
            game.save(update_fields=["total_seconds"])
            self.add_log(game, "game_minutes_changed", f"ゲーム時間を {minutes} 分に変更しました。")

    @database_sync_to_async
    def expire_question(self):
        """旧クライアントからの期限確認も、全体時間として受け付ける。"""
        with transaction.atomic():
            game = Game.objects.select_for_update().get(id=self.game_id)
            self.expire_if_needed(game)

    @database_sync_to_async
    def tick(self):
        """全画面から呼ばれる安全な時刻同期。問題紹介と全体タイマーを進める。"""
        with transaction.atomic():
            game = Game.objects.select_for_update().get(id=self.game_id)
            self.open_current_question_if_ready(game)
            self.advance_after_result_if_ready(game)
            self.expire_if_needed(game)

    @database_sync_to_async
    def validate_audio_playback(self):
        game, game_question = self.lock_current_game_question()
        if game_question.question.question_type != Question.QuestionType.AUDIO:
            raise ValueError("音当て問題ではありません。")
        if game.phase not in (Game.Phase.BUZZER_OPEN, Game.Phase.BUZZER_LOCKED):
            raise ValueError("現在は音声を再生できません。")

    def expire_if_needed(self, game):
        # game_started_at がない既存ゲームは、以前の「1問ごと」ルールで安全に完走させる。
        if not game.game_started_at:
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
            self.add_log(game, "question_expired", f"問題 {game.current_index + 1} の制限時間が終了しました。")
            return True
        if game.status != Game.Status.RUNNING or timezone.now() < game.game_started_at + timedelta(seconds=game.total_seconds):
            return False
        # 進行中の問題は時間切れ後も回答可能にし、次問へ進む時点で終了する。
        return False

    def lock_current_game_question(self):
        game = Game.objects.select_for_update().select_related("buzzed_player").get(id=self.game_id)
        game_question = GameQuestion.objects.select_related("question").get(game=game, position=game.current_index)
        return game, game_question

    def create_random_questions(self, game):
        if game.game_questions.exists():
            return
        eligible = Question.objects.filter(is_active=True, difficulty=game.difficulty)
        if game.selected_categories:
            eligible = eligible.filter(category__in=game.selected_categories)
        choice_count = (game.question_count + 1) // 2
        buzzer_count = game.question_count - choice_count
        choice_questions = list(eligible.filter(question_type__in=[Question.QuestionType.CHOICE, Question.QuestionType.IMAGE]).order_by("?")[:choice_count])
        buzzer_questions = list(eligible.filter(question_type__in=[Question.QuestionType.BUZZER, Question.QuestionType.AUDIO]).order_by("?")[:buzzer_count])
        candidates = choice_questions + buzzer_questions
        # 片方の形式が不足していても、重複なしで可能な限り設定された出題数を満たす。
        if len(candidates) < game.question_count:
            used_ids = [question.id for question in candidates]
            candidates.extend(eligible.exclude(id__in=used_ids).order_by("?")[: game.question_count - len(candidates)])
        if not candidates:
            raise ValueError("Adminで有効な問題を1問以上登録してください。")
        random.shuffle(candidates)
        GameQuestion.objects.bulk_create([GameQuestion(game=game, question=question, position=index) for index, question in enumerate(candidates)])

    def finish_game(self, game):
        game.status = Game.Status.FINISHED
        game.phase = Game.Phase.FINISHED
        game.buzzed_player = None
        game.result_advance_at = None
        game.question_open_at = None
        game.save(update_fields=["status", "phase", "buzzed_player", "question_open_at", "result_advance_at"])
        RankingEntry.objects.filter(game=game, round_number=game.round_number).delete()
        players = list(game.players.order_by("-score", "joined_at"))
        rankings, previous_score, previous_rank = [], None, 0
        for position, player in enumerate(players, start=1):
            rank = previous_rank if player.score == previous_score else position
            rankings.append(RankingEntry(game=game, player_name=player.nickname, score=player.score, rank=rank, round_number=game.round_number))
            previous_score, previous_rank = player.score, rank
        RankingEntry.objects.bulk_create(rankings)
        self.add_log(game, "game_finished", "ゲームを終了しました。")

    def add_log(self, game, event, message, player=None):
        GameLog.objects.create(game=game, event=event, message=message, player=player)

    @database_sync_to_async
    def get_state(self, include_admin=False, viewer_player_id=None):
        game = Game.objects.select_related("buzzed_player").get(id=self.game_id)
        players = list(game.players.order_by("-score", "slot"))
        game_questions = list(GameQuestion.objects.filter(game=game).select_related("question").order_by("position"))
        current_gq = next((item for item in game_questions if item.position == game.current_index), None)
        overtime = bool(game.status == Game.Status.RUNNING and game.game_started_at and current_gq and game.current_index == len(game_questions) - 1 and timezone.now() >= game.game_started_at + timedelta(seconds=game.total_seconds))
        question_data, answer_data = None, []
        if current_gq:
            question = current_gq.question
            is_intro_for_viewer = game.phase == Game.Phase.INTRO and not include_admin
            question_data = {"number": game.current_index + 1, "total": len(game_questions), "type": question.question_type, "category": question.category, "body": "" if is_intro_for_viewer else question.body, "choices": [] if is_intro_for_viewer else question.choices, "points": question.points, "image_url": "" if is_intro_for_viewer else (question.image.url if question.image else ""), "audio_url": "" if is_intro_for_viewer else (question.audio_file.url if question.audio_file else "")}
            if include_admin or game.phase in (Game.Phase.RESULT, Game.Phase.FINISHED):
                question_data.update({"correct_choice": question.correct_choice, "correct_text": question.correct_text or (question.choices[question.correct_choice - 1] if question.correct_choice else ""), "explanation": question.explanation})
                answer_data = list(current_gq.answers.select_related("player").values("player_id", "player__nickname", "selected_choice", "is_correct"))
                if include_admin:
                    for answer in answer_data:
                        answer["player_id"] = str(answer["player_id"])
                else:
                    for answer in answer_data:
                        answer.pop("player_id")
        answered_ids = list(current_gq.answers.values_list("player_id", flat=True)) if current_gq else []
        rankings = list(game.ranking_entries.filter(round_number=game.round_number).values("rank", "player_name", "score"))
        past_rankings = list(
            RankingEntry.objects.exclude(game=game, round_number=game.round_number)
            .order_by("-score", "rank", "created_at")
            .values("player_name", "score")[:5]
        )
        all_time_rankings = list(
            RankingEntry.objects.order_by("-score", "rank", "created_at")
            .values("player_name", "score")[:5]
        )
        previous_best = RankingEntry.objects.exclude(game=game, round_number=game.round_number).aggregate(best=Max("score"))["best"]
        current_best = rankings[0]["score"] if rankings else None
        buzzer_attempts = []
        if include_admin and current_gq:
            buzzer_attempts = list(current_gq.buzz_attempts.select_related("player").values("player__nickname", "is_correct", "score_delta", "buzzed_at"))
        logs = []
        if include_admin:
            logs = [{"id": item.id, "message": item.message, "created_at": item.created_at.strftime("%Y/%m/%d %H:%M:%S")} for item in game.logs.all()[:100]]
        my_answer = None
        if viewer_player_id and current_gq:
            my_answer = current_gq.answers.filter(player_id=viewer_player_id).values("selected_choice").first()
        return {"game": {"id": str(game.id), "title": game.title, "status": game.status, "phase": game.phase, "seconds": game.total_seconds, "minutes": max(1, game.total_seconds // 60), "deadline": (game.game_started_at + timedelta(seconds=game.total_seconds)).isoformat() if game.game_started_at else None, "intro_deadline": game.question_open_at.isoformat() if game.question_open_at else None, "result_advance_at": game.result_advance_at.isoformat() if game.result_advance_at else None, "buzzed_player_id": str(game.buzzed_player_id) if game.buzzed_player_id else None}, "question": question_data, "players": [{"id": str(p.id), "nickname": p.nickname, "slot": p.slot, "score": p.score, "connected": p.connected, "answered": str(p.id) in {str(answered) for answered in answered_ids}} for p in players], "answers": answer_data, "buzzer_attempts": buzzer_attempts, "logs": logs, "rankings": rankings, "past_rankings": past_rankings, "all_time_rankings": all_time_rankings, "is_new_record": current_best is not None and (previous_best is None or current_best > previous_best)}
