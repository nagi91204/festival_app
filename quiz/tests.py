from datetime import timedelta

from asgiref.sync import async_to_sync
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from .consumers import QuizConsumer
from .models import BuzzerAttempt, Game, GameLog, GamePlayer, GameQuestion, PlayerAnswer, Question, RankingEntry, TEACHER_QUIZ_CATEGORY


class QuestionValidationTests(TestCase):
    def test_choice_question_requires_two_or_four_choices(self):
        question = Question(title="問題", body="本文", choice_1="A", correct_choice=1)
        with self.assertRaises(ValidationError):
            question.full_clean()

    def test_valid_choice_question_is_accepted(self):
        question = Question(title="問題", body="本文", choice_1="A", choice_2="B", correct_choice=1)
        question.full_clean()

    def test_video_question_requires_video_file(self):
        question = Question(title="問題", body="本文", question_type=Question.QuestionType.VIDEO)
        with self.assertRaises(ValidationError):
            question.full_clean()

    def test_valid_video_question_is_accepted(self):
        question = Question(
            title="問題", body="本文", question_type=Question.QuestionType.VIDEO,
            video_file=SimpleUploadedFile("sample.mp4", b"dummy", content_type="video/mp4"),
        )
        question.full_clean()


class GameViewsTests(TestCase):
    def test_new_game_uses_only_game_time_and_opens_control(self):
        response = self.client.post("/game/new/", {"title": "  テスト  ", "question_count": "999", "seconds": "1"})
        game = Game.objects.get()
        self.assertRedirects(response, f"/control/{game.id}/?key={game.admin_token}")
        self.assertEqual(game.title, "テスト")
        self.assertEqual(game.question_count, 1)
        self.assertEqual(game.seconds_per_question, 5)

    def test_new_game_applies_question_limit(self):
        Question.objects.create(title="問題", body="本文", choice_1="A", choice_2="B", correct_choice=1, category="アニメ")
        response = self.client.post("/game/new/", {"title": "上限テスト", "minutes": "5", "max_questions": "7"})
        game = Game.objects.get(title="上限テスト")
        self.assertRedirects(response, f"/control/{game.id}/?key={game.admin_token}")
        self.assertEqual(game.max_questions, 7)
        self.assertTrue(GameLog.objects.filter(game=game, message__contains="出題数上限：7問").exists())

    def test_new_game_ignores_invalid_question_limit(self):
        self.client.post("/game/new/", {"title": "無効テスト", "minutes": "5", "max_questions": "abc"})
        game = Game.objects.get(title="無効テスト")
        self.assertEqual(game.max_questions, 0)

    def test_question_manager_requires_admin_key_and_registers_question(self):
        game = Game.objects.create()
        url = f"/control/{game.id}/questions/?key={game.admin_token}"
        self.assertEqual(self.client.get(f"/control/{game.id}/questions/").status_code, 404)
        response = self.client.post(url, {
            "title": "首都", "question_type": Question.QuestionType.CHOICE, "body": "日本の首都は？",
            "choice_1": "東京", "choice_2": "大阪", "correct_choice": 1, "difficulty": Question.Difficulty.NORMAL,
            "points": 20, "is_active": "on",
        })
        self.assertRedirects(response, url)
        self.assertTrue(Question.objects.filter(title="首都", points=20).exists())

    def test_ranking_page_is_available_for_a_game(self):
        game = Game.objects.create(title="順位テスト")

        response = self.client.get(f"/ranking/{game.id}/")

        self.assertContains(response, "プレイヤーランキング")
        self.assertContains(response, f'data-game-id="{game.id}"')
    def test_lobby_game_mode_can_be_changed_from_its_own_page(self):
        Question.objects.create(
            title="やさしいアニメ", body="本文", choice_1="A", choice_2="B", correct_choice=1,
            difficulty=Question.Difficulty.EASY, category="アニメ",
        )
        game = Game.objects.create()
        url = f"/control/{game.id}/mode/?key={game.admin_token}"

        response = self.client.post(url, {"categories": ["アニメ"]})

        self.assertRedirects(response, f"/control/{game.id}/?key={game.admin_token}")
        game.refresh_from_db()
        self.assertEqual(game.selected_categories, ["アニメ"])

    def test_mode_page_shows_category_counts_and_saves_question_limit(self):
        Question.objects.create(title="アニメ1", body="本文", choice_1="A", choice_2="B", correct_choice=1, category="アニメ")
        Question.objects.create(title="アニメ2", body="本文", choice_1="A", choice_2="B", correct_choice=1, category="アニメ")
        Question.objects.create(title="音楽1", body="本文", choice_1="A", choice_2="B", correct_choice=1, category="音楽")
        game = Game.objects.create()
        url = f"/control/{game.id}/mode/?key={game.admin_token}"

        page = self.client.get(url)
        self.assertContains(page, "出題内容を変更")
        self.assertContains(page, "2 問")
        self.assertContains(page, "name=\"max_questions\"")

        response = self.client.post(url, {"categories": ["アニメ"], "max_questions": "5"})
        self.assertRedirects(response, f"/control/{game.id}/?key={game.admin_token}")
        game.refresh_from_db()
        self.assertEqual(game.max_questions, 5)
        self.assertTrue(GameLog.objects.filter(game=game, message__contains="上限：5問").exists())

    def test_question_limit_ignores_invalid_values(self):
        Question.objects.create(title="問題", body="本文", choice_1="A", choice_2="B", correct_choice=1, category="一般")
        game = Game.objects.create()
        url = f"/control/{game.id}/mode/?key={game.admin_token}"
        self.client.post(url, {"categories": ["一般"], "max_questions": "abc"})
        game.refresh_from_db()
        self.assertEqual(game.max_questions, 0)


class JoinCodeTests(TestCase):
    def test_created_games_get_unique_join_codes_automatically(self):
        game = Game.objects.create()
        other = Game.objects.create()
        self.assertTrue(game.join_code.isdigit())
        self.assertNotEqual(game.join_code, other.join_code)

    def test_home_shows_join_code_card(self):
        response = self.client.get("/")
        self.assertContains(response, "join-code-input")
        self.assertContains(response, "既存のゲームに参加する")

    def test_join_redirects_to_player_screen(self):
        game = Game.objects.create()
        response = self.client.post("/join/", {"code": game.join_code})
        self.assertRedirects(response, f"/player/{game.id}/", fetch_redirect_response=False)

    def test_join_accepts_leading_zeros_and_non_digits(self):
        game = Game.objects.create()
        zero_padded = f"{int(game.join_code):04d}"
        response = self.client.post("/join/", {"code": f" {zero_padded} "})
        self.assertRedirects(response, f"/player/{game.id}/", fetch_redirect_response=False)

    def test_join_rejects_unknown_code(self):
        response = self.client.post("/join/", {"code": "9999"})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "見つかりません", status_code=400)

    def test_join_rejects_finished_game(self):
        game = Game.objects.create(status=Game.Status.FINISHED, phase=Game.Phase.FINISHED)
        response = self.client.post("/join/", {"code": game.join_code})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "終了", status_code=400)

    def test_join_shortcut_url_redirects_to_player_screen(self):
        game = Game.objects.create()
        response = self.client.get(f"/j/{game.join_code}/")
        self.assertRedirects(response, f"/player/{game.id}/", fetch_redirect_response=False)


class ConsumerTransitionTests(TestCase):
    def test_all_categories_excludes_teacher_quizzes(self):
        regular = Question.objects.create(
            title="一般問題", body="本文", choice_1="A", choice_2="B", correct_choice=1, category="一般"
        )
        teacher = Question.objects.create(
            title="先生問題", body="本文", choice_1="A", choice_2="B", correct_choice=1,
            category=TEACHER_QUIZ_CATEGORY,
        )
        game = Game.objects.create()
        consumer = QuizConsumer()
        consumer.game_id = str(game.id)

        async_to_sync(consumer.start_next_question)()

        question_ids = game.game_questions.values_list("question_id", flat=True)
        self.assertIn(regular.id, question_ids)
        self.assertNotIn(teacher.id, question_ids)
        self.assertFalse(
            game.game_questions.filter(question__category=TEACHER_QUIZ_CATEGORY).exists()
        )

    def test_teacher_quizzes_are_included_when_explicitly_selected(self):
        Question.objects.create(
            title="一般問題", body="本文", choice_1="A", choice_2="B", correct_choice=1, category="一般"
        )
        teacher = Question.objects.create(
            title="先生問題", body="本文", choice_1="A", choice_2="B", correct_choice=1,
            category=TEACHER_QUIZ_CATEGORY,
        )
        game = Game.objects.create(selected_categories=[TEACHER_QUIZ_CATEGORY])
        consumer = QuizConsumer()
        consumer.game_id = str(game.id)

        async_to_sync(consumer.start_next_question)()

        self.assertIn(teacher.id, game.game_questions.values_list("question_id", flat=True))
        self.assertTrue(
            game.game_questions.filter(question__category=TEACHER_QUIZ_CATEGORY).exists()
        )
        self.assertFalse(
            game.game_questions.exclude(question__category=TEACHER_QUIZ_CATEGORY).exists()
        )

    def test_game_finishes_when_question_pool_is_exhausted(self):
        """出題対象を使い切ったら、制限時間が残っていてもゲームを終了する。"""
        category = "問題数有限テスト"
        Question.objects.create(title="問題1", body="本文", choice_1="A", choice_2="B", correct_choice=1, category=category)
        Question.objects.create(title="問題2", body="本文", choice_1="A", choice_2="B", correct_choice=1, category=category)
        game = Game.objects.create(selected_categories=[category])
        consumer = QuizConsumer()
        consumer.game_id = str(game.id)

        async_to_sync(consumer.start_next_question)()
        game.refresh_from_db()
        self.assertEqual(game.game_questions.count(), 2)
        self.assertEqual(game.current_index, 0)

        game.current_index = 1
        game.phase = Game.Phase.RESULT
        game.save(update_fields=["current_index", "phase"])
        async_to_sync(consumer.start_next_question)()

        game.refresh_from_db()
        self.assertEqual(game.status, Game.Status.FINISHED)
        self.assertEqual(game.phase, Game.Phase.FINISHED)
        self.assertEqual(game.current_index, 1)
        self.assertEqual(game.game_questions.count(), 2)

    def test_question_limit_caps_pool_and_ends_game_at_the_limit(self):
        """上限が設定されたら、その問題数を出題し終えた時点でゲームを終了する。"""
        category = "上限テスト"
        for number in range(1, 5):
            Question.objects.create(title=f"問題{number}", body="本文", choice_1="A", choice_2="B", correct_choice=1, category=category)
        game = Game.objects.create(selected_categories=[category], max_questions=2)
        consumer = QuizConsumer()
        consumer.game_id = str(game.id)

        async_to_sync(consumer.start_next_question)()
        game.refresh_from_db()
        self.assertEqual(game.game_questions.count(), 2)  # 4問あっても2問だけ作る

        game.current_index = 1
        game.phase = Game.Phase.RESULT
        game.save(update_fields=["current_index", "phase"])
        async_to_sync(consumer.start_next_question)()

        game.refresh_from_db()
        self.assertEqual(game.status, Game.Status.FINISHED)
        self.assertEqual(game.game_questions.count(), 2)

    def test_close_answers_uses_a_transaction_and_changes_phase(self):
        question = Question.objects.create(title="問題", body="本文", choice_1="A", choice_2="B", correct_choice=1)
        game = Game.objects.create(status=Game.Status.RUNNING, phase=Game.Phase.QUESTION, current_index=0)
        GameQuestion.objects.create(game=game, question=question, position=0)
        consumer = QuizConsumer()
        consumer.game_id = str(game.id)

        async_to_sync(consumer.close_answers)()

        game.refresh_from_db()
        self.assertEqual(game.phase, Game.Phase.ANSWER_CLOSED)

    def test_expired_choice_question_is_closed(self):
        game = Game.objects.create(
            status=Game.Status.RUNNING,
            phase=Game.Phase.QUESTION,
            question_started_at=timezone.now() - timedelta(seconds=21),
            seconds_per_question=20,
        )
        consumer = QuizConsumer()
        consumer.game_id = str(game.id)

        async_to_sync(consumer.expire_question)()

        game.refresh_from_db()
        self.assertEqual(game.phase, Game.Phase.ANSWER_CLOSED)

    def test_all_connected_players_answering_starts_timed_result(self):
        # 4択は早押し形式のため、全員同時回答の自動締め切りは画像予想が対象。
        question = Question.objects.create(title="問題", body="本文", question_type=Question.QuestionType.IMAGE, choice_1="A", choice_2="B", correct_choice=1)
        game = Game.objects.create(status=Game.Status.RUNNING, phase=Game.Phase.QUESTION, current_index=0)
        game_question = GameQuestion.objects.create(game=game, question=question, position=0)
        first = GamePlayer.objects.create(game=game, nickname="一人目", slot=1, connected=True)
        second = GamePlayer.objects.create(game=game, nickname="二人目", slot=2, connected=True)
        PlayerAnswer.objects.create(game_question=game_question, player=first, selected_choice=1, is_correct=True)
        PlayerAnswer.objects.create(game_question=game_question, player=second, selected_choice=2, is_correct=False)
        consumer = QuizConsumer()

        self.assertTrue(consumer.start_auto_result_if_all_answered(game, game_question))

        game.refresh_from_db()
        self.assertEqual(game.phase, Game.Phase.RESULT)
        self.assertIsNotNone(game.result_advance_at)

    def test_end_game_creates_rankings_and_clears_automatic_transition(self):
        game = Game.objects.create(status=Game.Status.RUNNING, phase=Game.Phase.RESULT, result_advance_at=timezone.now())
        GamePlayer.objects.create(game=game, nickname="一人目", slot=1, score=20)
        consumer = QuizConsumer()
        consumer.game_id = str(game.id)

        async_to_sync(consumer.end_game)()

        game.refresh_from_db()
        self.assertEqual(game.phase, Game.Phase.FINISHED)
        self.assertIsNone(game.result_advance_at)
        self.assertEqual(RankingEntry.objects.filter(game=game).count(), 1)

    def test_reset_game_returns_to_lobby_and_removes_previous_players(self):
        game = Game.objects.create(status=Game.Status.FINISHED, phase=Game.Phase.FINISHED, current_index=0)
        question = Question.objects.create(title="問題", body="本文", choice_1="A", choice_2="B", correct_choice=1)
        GameQuestion.objects.create(game=game, question=question, position=0)
        GamePlayer.objects.create(game=game, nickname="一人目", slot=1, score=20)
        RankingEntry.objects.create(game=game, player_name="一人目", score=20, rank=1)
        consumer = QuizConsumer()
        consumer.game_id = str(game.id)

        async_to_sync(consumer.reset_game)()

        game.refresh_from_db()
        self.assertEqual(game.status, Game.Status.LOBBY)
        self.assertEqual(game.phase, Game.Phase.LOBBY)
        self.assertEqual(game.current_index, -1)
        self.assertFalse(game.players.exists())
        self.assertFalse(game.game_questions.exists())
        self.assertEqual(game.round_number, 2)
        self.assertEqual(game.ranking_entries.count(), 1)

    def test_state_includes_historical_high_scores_from_other_games(self):
        game = Game.objects.create(round_number=2)
        RankingEntry.objects.create(game=game, player_name="前回の王者", score=90, rank=1, round_number=1)
        previous_game = Game.objects.create(status=Game.Status.FINISHED, phase=Game.Phase.FINISHED)
        RankingEntry.objects.create(game=previous_game, player_name="過去の王者", score=80, rank=1)
        consumer = QuizConsumer()
        consumer.game_id = str(game.id)

        state = async_to_sync(consumer.get_state)(False, None)

        self.assertEqual(state["past_rankings"], [
            {"player_name": "前回の王者", "score": 90},
            {"player_name": "過去の王者", "score": 80},
        ])


class VideoQuestionFlowTests(TestCase):
    def _video_game(self, **game_kwargs):
        question = Question.objects.create(
            title="動画問題", body="この動画は何？", question_type=Question.QuestionType.VIDEO,
            video_file=SimpleUploadedFile("sample.mp4", b"dummy", content_type="video/mp4"),
        )
        game = Game.objects.create(status=Game.Status.RUNNING, **game_kwargs)
        game_question = GameQuestion.objects.create(game=game, question=question, position=0)
        return game, game_question

    def test_video_question_opens_as_buzzer_phase(self):
        game, _ = self._video_game(phase=Game.Phase.INTRO, current_index=0)
        consumer = QuizConsumer()
        consumer.game_id = str(game.id)

        consumer.open_current_question(game)

        game.refresh_from_db()
        self.assertEqual(game.phase, Game.Phase.BUZZER_OPEN)

    def test_open_buzzer_allows_video_question(self):
        game, _ = self._video_game(phase=Game.Phase.BUZZER_LOCKED, current_index=0)
        consumer = QuizConsumer()
        consumer.game_id = str(game.id)

        async_to_sync(consumer.open_buzzer)()

        game.refresh_from_db()
        self.assertEqual(game.phase, Game.Phase.BUZZER_OPEN)

    def test_play_video_action_validates_for_video_question(self):
        game, _ = self._video_game(phase=Game.Phase.BUZZER_OPEN, current_index=0)
        consumer = QuizConsumer()
        consumer.game_id = str(game.id)

        async_to_sync(consumer.validate_video_playback)()

        self.assertTrue(True)  # 例外が出ずに検証を通過すればよい

    def test_play_video_is_rejected_for_audio_question(self):
        question = Question.objects.create(
            title="音問題", body="この音は何？", question_type=Question.QuestionType.AUDIO,
            audio_file=SimpleUploadedFile("sample.mp3", b"dummy", content_type="audio/mpeg"),
        )
        game = Game.objects.create(status=Game.Status.RUNNING, phase=Game.Phase.BUZZER_OPEN, current_index=0)
        GameQuestion.objects.create(game=game, question=question, position=0)
        consumer = QuizConsumer()
        consumer.game_id = str(game.id)

        with self.assertRaises(ValueError):
            async_to_sync(consumer.validate_video_playback)()

    def test_video_questions_join_the_buzzer_pool(self):
        question = Question.objects.create(
            title="動画問題", body="この動画は何？", question_type=Question.QuestionType.VIDEO,
            video_file=SimpleUploadedFile("sample.mp4", b"dummy", content_type="video/mp4"),
        )
        game = Game.objects.create(status=Game.Status.LOBBY, question_count=2)
        consumer = QuizConsumer()
        consumer.game_id = str(game.id)

        consumer.create_random_questions(game)

        self.assertIn(question, [gq.question for gq in game.game_questions.all()])

    def test_state_includes_video_url_for_video_question(self):
        game, _ = self._video_game(phase=Game.Phase.BUZZER_OPEN, current_index=0)
        consumer = QuizConsumer()
        consumer.game_id = str(game.id)

        state = async_to_sync(consumer.get_state)(False, None)

        self.assertEqual(state["question"]["type"], Question.QuestionType.VIDEO)
        self.assertTrue(state["question"]["video_url"].endswith(".mp4"))


class ChoiceBuzzerFlowTests(TestCase):
    """4択は早押し形式で行う: 押したら3秒以内に口頭回答、外れたらお手つき。"""

    def _choice_game(self, **game_kwargs):
        question = Question.objects.create(
            title="4択問題", body="この都道府県は？", question_type=Question.QuestionType.CHOICE,
            choice_1="東京都", choice_2="大阪府", choice_3="北海道", choice_4="沖縄県", correct_choice=3)
        game = Game.objects.create(status=Game.Status.RUNNING, **game_kwargs)
        game_question = GameQuestion.objects.create(game=game, question=question, position=0)
        return game, game_question

    def test_choice_question_opens_as_buzzer_phase(self):
        game, _ = self._choice_game(phase=Game.Phase.INTRO, current_index=0)
        consumer = QuizConsumer()
        consumer.game_id = str(game.id)

        consumer.open_current_question(game)

        game.refresh_from_db()
        self.assertEqual(game.phase, Game.Phase.BUZZER_OPEN)

    def test_buzz_on_choice_question_sets_three_second_deadline(self):
        game, game_question = self._choice_game(phase=Game.Phase.BUZZER_OPEN, current_index=0)
        player = GamePlayer.objects.create(game=game, nickname="回答者", slot=1)
        consumer = QuizConsumer()
        consumer.game_id = str(game.id)
        consumer.player_id = str(player.id)

        async_to_sync(consumer.buzz)()

        game.refresh_from_db()
        self.assertEqual(game.phase, Game.Phase.BUZZER_LOCKED)
        self.assertEqual(game.buzzed_player, player)
        self.assertIsNotNone(game.buzz_deadline_at)
        remaining = (game.buzz_deadline_at - timezone.now()).total_seconds()
        self.assertAlmostEqual(remaining, 3, delta=1)

    def test_buzz_deadline_passes_without_judgment_keeps_waiting_for_host(self):
        """3秒経過しても自動お手つきにはならず、司会の判定を無制限に待つ。"""
        game, game_question = self._choice_game(phase=Game.Phase.BUZZER_LOCKED, current_index=0)
        player = GamePlayer.objects.create(game=game, nickname="回答者", slot=1, connected=True)
        BuzzerAttempt.objects.create(game_question=game_question, player=player)
        game.buzzed_player = player
        game.buzz_deadline_at = timezone.now() - timedelta(seconds=1)
        game.save(update_fields=["buzzed_player", "buzz_deadline_at"])
        consumer = QuizConsumer()
        consumer.game_id = str(game.id)

        async_to_sync(consumer.tick)()

        game.refresh_from_db()
        self.assertEqual(game.phase, Game.Phase.BUZZER_LOCKED)
        self.assertEqual(game.buzzed_player, player)
        # 締切を過ぎても司会の判定は無制限にできる。
        async_to_sync(consumer.judge_buzzer)(True)
        game.refresh_from_db()
        self.assertEqual(game.phase, Game.Phase.RESULT)

    def test_all_players_judged_wrong_auto_advance_to_result(self):
        """全員が不正解判定（お手つき）になったら自動で正解発表へ。"""
        game, game_question = self._choice_game(phase=Game.Phase.BUZZER_LOCKED, current_index=0)
        first = GamePlayer.objects.create(game=game, nickname="一人目", slot=1, connected=True)
        second = GamePlayer.objects.create(game=game, nickname="二人目", slot=2, connected=True)
        BuzzerAttempt.objects.create(game_question=game_question, player=first)
        game.buzzed_player = first
        game.save(update_fields=["buzzed_player"])
        consumer = QuizConsumer()
        consumer.game_id = str(game.id)

        async_to_sync(consumer.judge_buzzer)(False)
        game.refresh_from_db()
        self.assertEqual(game.phase, Game.Phase.BUZZER_OPEN)

        # 二人目が押して不正解 → 全員お手つきで自動進行。
        consumer.player_id = str(second.id)
        async_to_sync(consumer.buzz)()
        async_to_sync(consumer.judge_buzzer)(False)

        game.refresh_from_db()
        self.assertEqual(game.phase, Game.Phase.RESULT)
        self.assertIsNotNone(game.result_advance_at)

    def test_judged_wrong_player_cannot_buzz_again(self):
        game, game_question = self._choice_game(phase=Game.Phase.BUZZER_LOCKED, current_index=0)
        player = GamePlayer.objects.create(game=game, nickname="回答者", slot=1, connected=True)
        GamePlayer.objects.create(game=game, nickname="二人目", slot=2, connected=True)
        BuzzerAttempt.objects.create(game_question=game_question, player=player)
        game.buzzed_player = player
        game.save(update_fields=["buzzed_player"])
        consumer = QuizConsumer()
        consumer.game_id = str(game.id)
        consumer.player_id = str(player.id)

        async_to_sync(consumer.judge_buzzer)(False)

        game.refresh_from_db()
        self.assertEqual(game.phase, Game.Phase.BUZZER_OPEN)
        attempt = game_question.buzz_attempts.get(player=player)
        self.assertFalse(attempt.is_correct)
        self.assertIsNone(game.buzz_deadline_at)
        with self.assertRaises(ValueError):
            async_to_sync(consumer.buzz)()

    def test_state_marks_players_who_already_buzzed(self):
        game, game_question = self._choice_game(phase=Game.Phase.BUZZER_OPEN, current_index=0)
        player = GamePlayer.objects.create(game=game, nickname="回答者", slot=1)
        BuzzerAttempt.objects.create(game_question=game_question, player=player, is_correct=False)
        consumer = QuizConsumer()
        consumer.game_id = str(game.id)

        state = async_to_sync(consumer.get_state)(False, None)

        self.assertTrue(state["players"][0]["buzzed"])

class StateJsonSerializableTests(TestCase):
    """司会・参加者の state は必ず JSON 化できる。datetime の混入を防ぐ回帰テスト。"""

    def test_admin_state_with_buzz_attempt_is_json_serializable(self):
        import json

        question = Question.objects.create(
            title="4択問題", body="この都道府県は？", question_type=Question.QuestionType.CHOICE,
            choice_1="東京都", choice_2="大阪府", correct_choice=1)
        game = Game.objects.create(status=Game.Status.RUNNING, phase=Game.Phase.BUZZER_LOCKED, current_index=0)
        game_question = GameQuestion.objects.create(game=game, question=question, position=0)
        player = GamePlayer.objects.create(game=game, nickname="回答者", slot=1)
        BuzzerAttempt.objects.create(game_question=game_question, player=player, is_correct=False)
        consumer = QuizConsumer()
        consumer.game_id = str(game.id)

        for is_admin in (False, True):
            with self.subTest(is_admin=is_admin):
                state = async_to_sync(consumer.get_state)(is_admin, str(player.id))
                json.dumps({"type": "state", "state": state})
