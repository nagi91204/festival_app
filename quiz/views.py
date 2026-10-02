from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Game
from .forms import QuestionForm


def home(request):
    return render(request, "quiz/home.html")


@require_POST
def new_game(request):
    title = request.POST.get("title", "文化祭クイズ").strip()[:100] or "文化祭クイズ"
    try:
        question_count = max(1, min(int(request.POST.get("question_count", 10)), 100))
        seconds = max(5, min(int(request.POST.get("seconds", 20)), 120))
    except (TypeError, ValueError):
        question_count, seconds = 10, 20
    game = Game.objects.create(title=title, question_count=question_count, seconds_per_question=seconds)
    return redirect(f"{reverse('quiz:control', kwargs={'game_id': game.id})}?key={game.admin_token}")


def game_or_404(game_id):
    return get_object_or_404(Game, id=game_id)


def control(request, game_id):
    game = admin_game_or_404(request, game_id)
    return render(request, "quiz/control.html", {"game": game})


def display(request, game_id):
    return render(request, "quiz/display.html", {"game": game_or_404(game_id)})


def player(request, game_id):
    return render(request, "quiz/player.html", {"game": game_or_404(game_id)})


def admin_game_or_404(request, game_id):
    game = game_or_404(game_id)
    if request.GET.get("key") != str(game.admin_token):
        raise Http404("管理者用URLが正しくありません。")
    return game


def question_manager(request, game_id):
    game = admin_game_or_404(request, game_id)
    if request.method == "POST":
        form = QuestionForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect(f"{reverse('quiz:question_manager', kwargs={'game_id': game.id})}?key={game.admin_token}")
    else:
        form = QuestionForm(initial={"points": 10, "is_active": True})
    return render(request, "quiz/question_manager.html", {"game": game, "form": form})
