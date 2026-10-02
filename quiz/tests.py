from datetime import timedelta

from asgiref.sync import async_to_sync
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from .consumers import QuizConsumer
from .models import Game, GamePlayer, GameQuestion, PlayerAnswer, Question, RankingEntry


class QuestionValidationTests(TestCase):
    def test_choice_question_requires_two_or_four_choices(self):
        question = Question(title="問題", body="本文", choice_1="A", correct_choice=1)
        with self.assertRaises(ValidationError):
            question.full_clean()

    def test_valid_choice_question_is_accepted(self):
        question = Question(title="問題", body="本文", choice_1="A", choice_2="B", correct_choice=1)
        question.full_clean()


class GameViewsTests(TestCase):
    def test_new_game_clamps_invalid_values_and_opens_control(self):
        response = self.client.post("/game/new/", {"title": "  テスト  ", "question_count": "999", "seconds": "1"})
        game = Game.objects.get()
        self.assertRedirects(response, f"/control/{game.id}/?key={game.admin_token}")
        self.assertEqual(game.title, "テスト")
        self.assertEqual(game.question_count, 100)
        self.assertEqual(game.seconds_per_question, 5)

    def test_question_manager_requires_admin_key_and_registers_question(self):
        game = Game.objects.create()
        url = f"/control/{game.id}/questions/?key={game.admin_token}"
        self.assertEqual(self.client.get(f"/control/{game.id}/questions/").status_code, 404)
        response = self.client.post(url, {
            "title": "首都", "question_type": Question.QuestionType.CHOICE, "body": "日本の首都は？",
            "choice_1": "東京", "choice_2": "大阪", "correct_choice": 1, "points": 20, "is_active": "on",
        })
        self.assertRedirects(response, url)
        self.assertTrue(Question.objects.filter(title="首都", points=20).exists())


class ConsumerTransitionTests(TestCase):
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
        question = Question.objects.create(title="問題", body="本文", choice_1="A", choice_2="B", correct_choice=1)
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
