import uuid

from django.core.exceptions import ValidationError
from django.db import models


class Question(models.Model):
    """Adminで登録する問題。選択式・早押し・音当てに共通で使う。"""

    class QuestionType(models.TextChoices):
        CHOICE = "choice", "2択・4択"
        BUZZER = "buzzer", "早押し"
        AUDIO = "audio", "音当て"
        VIDEO = "video", "動画当て"
        IMAGE = "image", "画像予想"

    class Difficulty(models.TextChoices):
        EASY = "easy", "簡単"
        NORMAL = "normal", "普通"
        HARD = "hard", "ハード"

    title = models.CharField("管理用タイトル", max_length=100)
    question_type = models.CharField("問題形式", max_length=10, choices=QuestionType.choices, default=QuestionType.CHOICE)
    category = models.CharField("カテゴリ", max_length=50, blank=True)
    difficulty = models.CharField("難易度", max_length=10, choices=Difficulty.choices, default=Difficulty.NORMAL)
    body = models.TextField("問題文")
    choice_1 = models.CharField("選択肢1", max_length=200, blank=True)
    choice_2 = models.CharField("選択肢2", max_length=200, blank=True)
    choice_3 = models.CharField("選択肢3", max_length=200, blank=True)
    choice_4 = models.CharField("選択肢4", max_length=200, blank=True)
    correct_choice = models.PositiveSmallIntegerField("正解の番号", null=True, blank=True)
    correct_text = models.CharField("正解表示・口頭回答の正解", max_length=300, blank=True)
    explanation = models.TextField("解説", blank=True)
    image = models.ImageField("問題画像", upload_to="questions/images/", blank=True)
    audio_file = models.FileField("音声ファイル", upload_to="questions/audio/", blank=True)
    video_file = models.FileField("動画ファイル", upload_to="questions/videos/", blank=True)
    points = models.PositiveIntegerField("正解時の得点", default=10)
    is_active = models.BooleanField("出題に使う", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.get_question_type_display()}] {self.title}"

    @property
    def choices(self):
        return [value for value in [self.choice_1, self.choice_2, self.choice_3, self.choice_4] if value]

    def clean(self):
        if self.question_type == self.QuestionType.CHOICE:
            if len(self.choices) not in (2, 4):
                raise ValidationError("選択式では選択肢を2個または4個入力してください。")
            if not self.correct_choice or self.correct_choice > len(self.choices):
                raise ValidationError("正解の番号を選択肢の範囲内で入力してください。")
        if self.question_type == self.QuestionType.AUDIO and not self.audio_file:
            raise ValidationError("音当て問題には音声ファイルを登録してください。")
        if self.question_type == self.QuestionType.VIDEO and not self.video_file:
            raise ValidationError("動画当て問題には動画ファイルを登録してください。")
        if self.question_type == self.QuestionType.IMAGE and not self.image:
            raise ValidationError("画像予想問題には画像を登録してください。")


class Game(models.Model):
    class Status(models.TextChoices):
        LOBBY = "lobby", "待機中"
        RUNNING = "running", "進行中"
        FINISHED = "finished", "終了"

    class Phase(models.TextChoices):
        LOBBY = "lobby", "待機"
        INTRO = "intro", "問題紹介"
        QUESTION = "question", "問題・回答中"
        ANSWER_CLOSED = "answer_closed", "回答締切"
        BUZZER_OPEN = "buzzer_open", "早押し受付中"
        BUZZER_LOCKED = "buzzer_locked", "司会判定中"
        RESULT = "result", "結果発表"
        FINISHED = "finished", "終了"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin_token = models.UUIDField(default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=100, default="文化祭クイズ")
    max_players = models.PositiveSmallIntegerField(default=5)
    question_count = models.PositiveSmallIntegerField(default=10)
    seconds_per_question = models.PositiveSmallIntegerField(default=20)
    total_seconds = models.PositiveIntegerField(default=300)
    difficulty = models.CharField(max_length=10, choices=Question.Difficulty.choices, default=Question.Difficulty.NORMAL)
    selected_categories = models.JSONField(default=list, blank=True)
    round_number = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.LOBBY)
    phase = models.CharField(max_length=20, choices=Phase.choices, default=Phase.LOBBY)
    current_index = models.IntegerField(default=-1)
    question_started_at = models.DateTimeField(null=True, blank=True)
    game_started_at = models.DateTimeField(null=True, blank=True)
    question_open_at = models.DateTimeField(null=True, blank=True)
    result_advance_at = models.DateTimeField(null=True, blank=True)
    buzzed_player = models.ForeignKey("GamePlayer", null=True, blank=True, on_delete=models.SET_NULL, related_name="current_buzz_games")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({str(self.id)[:8]})"


class GameQuestion(models.Model):
    """このゲームでの出題順。Questionをランダムに一度だけ並べる。"""

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="game_questions")
    question = models.ForeignKey(Question, on_delete=models.PROTECT)
    position = models.PositiveSmallIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["game", "position"], name="unique_game_position"),
            models.UniqueConstraint(fields=["game", "question"], name="no_duplicate_question_in_game"),
        ]
        ordering = ["position"]


class GamePlayer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="players")
    nickname = models.CharField(max_length=20)
    slot = models.PositiveSmallIntegerField()
    score = models.IntegerField(default=0)
    connected = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["game", "nickname"], name="unique_nickname_in_game"),
            models.UniqueConstraint(fields=["game", "slot"], name="unique_slot_in_game"),
        ]
        ordering = ["slot"]

    def __str__(self):
        return self.nickname


class PlayerAnswer(models.Model):
    game_question = models.ForeignKey(GameQuestion, on_delete=models.CASCADE, related_name="answers")
    player = models.ForeignKey(GamePlayer, on_delete=models.CASCADE, related_name="answers")
    selected_choice = models.PositiveSmallIntegerField()
    is_correct = models.BooleanField()
    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["game_question", "player"], name="one_choice_answer_per_player")]


class BuzzerAttempt(models.Model):
    game_question = models.ForeignKey(GameQuestion, on_delete=models.CASCADE, related_name="buzz_attempts")
    player = models.ForeignKey(GamePlayer, on_delete=models.CASCADE, related_name="buzz_attempts")
    is_correct = models.BooleanField(null=True, blank=True)
    score_delta = models.IntegerField(default=0)
    buzzed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["game_question", "player"], name="one_buzz_per_player")]
        ordering = ["buzzed_at"]


class RankingEntry(models.Model):
    """ゲーム終了時点の順位を保存するためのスナップショット。"""

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="ranking_entries")
    player_name = models.CharField(max_length=20)
    score = models.IntegerField()
    rank = models.PositiveSmallIntegerField()
    round_number = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["rank"]


class GameLog(models.Model):
    """司会画面で確認する、ゲーム内で起きた操作と参加者の履歴。"""

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="logs")
    player = models.ForeignKey(GamePlayer, null=True, blank=True, on_delete=models.SET_NULL, related_name="game_logs")
    event = models.CharField(max_length=40)
    message = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.game}: {self.message}"
