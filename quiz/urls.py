from django.urls import path

from . import views

app_name = "quiz"

urlpatterns = [
    path("", views.home, name="home"),
    path("game/new/", views.new_game, name="new_game"),
    path("control/<uuid:game_id>/", views.control, name="control"),
    path("control/<uuid:game_id>/mode/", views.edit_game_mode, name="edit_game_mode"),
    path("control/<uuid:game_id>/questions/", views.question_manager, name="question_manager"),
    path("control/<uuid:game_id>/questions/<int:question_id>/delete/", views.question_delete, name="question_delete"),
    path("control/<uuid:game_id>/logs/", views.game_logs, name="game_logs"),
    path("display/<uuid:game_id>/", views.display, name="display"),
    path("ranking/<uuid:game_id>/", views.ranking, name="ranking"),
    path("player/<uuid:game_id>/", views.player, name="player"),
]
