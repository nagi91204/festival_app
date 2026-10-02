from django.urls import path

from . import views

app_name = "quiz"

urlpatterns = [
    path("", views.home, name="home"),
    path("game/new/", views.new_game, name="new_game"),
    path("control/<uuid:game_id>/", views.control, name="control"),
    path("control/<uuid:game_id>/questions/", views.question_manager, name="question_manager"),
    path("display/<uuid:game_id>/", views.display, name="display"),
    path("player/<uuid:game_id>/", views.player, name="player"),
]
