from datetime import timedelta

from asgiref.sync import async_to_sync
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from .consumers import QuizConsumer
from .models import Game, GameQuestion, Question


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
