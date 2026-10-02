from django.urls import re_path

from .consumers import QuizConsumer

websocket_urlpatterns = [
    re_path(r"ws/quiz/(?P<game_id>[0-9a-f-]+)/$", QuizConsumer.as_asgi()),
    re_path(r"ws/quiz/(?P<game_id>[0-9a-f-]+)/admin/$", QuizConsumer.as_asgi()),
]
