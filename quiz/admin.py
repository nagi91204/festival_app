from django.contrib import admin

from .models import BuzzerAttempt, Game, GamePlayer, GameQuestion, PlayerAnswer, Question, RankingEntry


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("title", "question_type", "category", "difficulty", "points", "is_active", "created_at")
    list_filter = ("question_type", "category", "difficulty", "is_active")
    search_fields = ("title", "body", "correct_text")
    fieldsets = (
        ("基本", {"fields": ("title", "question_type", "category", "difficulty", "body", "points", "is_active")}),
        ("選択式", {"fields": ("choice_1", "choice_2", "choice_3", "choice_4", "correct_choice")}),
        ("早押し・音当ての答え", {"fields": ("correct_text", "explanation")}),
        ("メディア", {"fields": ("image", "audio_file", "video_file")}),
    )


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "phase", "question_count", "created_at")
    readonly_fields = ("id", "current_index", "question_started_at", "buzzed_player")


admin.site.register(GameQuestion)
admin.site.register(GamePlayer)
admin.site.register(PlayerAnswer)
admin.site.register(BuzzerAttempt)
admin.site.register(RankingEntry)
