from django.db.models import Count
from django.db.models.deletion import ProtectedError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Game, GameLog, Question
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
    GameLog.objects.create(game=game, event="game_created", message="ゲームを作成しました。")
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
    edit_id = request.GET.get("edit")
    editing_question = None
    if edit_id:
        editing_question = get_object_or_404(Question, pk=edit_id)
    if request.method == "POST":
        form = QuestionForm(request.POST, request.FILES, instance=editing_question)
        if form.is_valid():
            form.save()
            return redirect(f"{reverse('quiz:question_manager', kwargs={'game_id': game.id})}?key={game.admin_token}")
    else:
        form = QuestionForm(instance=editing_question, initial=None if editing_question else {"points": 10, "is_active": True})
    questions = Question.objects.annotate(game_count=Count("gamequestion")).order_by("-created_at")
    return render(request, "quiz/question_manager.html", {
        "game": game, "form": form, "questions": questions, "editing_question": editing_question,
    })


@require_POST
def question_delete(request, game_id, question_id):
    game = admin_game_or_404(request, game_id)
    question = get_object_or_404(Question, pk=question_id)
    error = ""
    try:
        question.delete()
        return redirect(f"{reverse('quiz:question_manager', kwargs={'game_id': game.id})}?key={game.admin_token}")
    except ProtectedError:
        error = "この問題はすでにゲームに使用されているため削除できません。出題に使わない場合は「出題に使う」をオフにしてください。"
    form = QuestionForm(initial={"points": 10, "is_active": True})
    questions = Question.objects.annotate(game_count=Count("gamequestion")).order_by("-created_at")
    return render(request, "quiz/question_manager.html", {"game": game, "form": form, "questions": questions, "manager_error": error})


def game_logs(request, game_id):
    game = admin_game_or_404(request, game_id)
    logs = GameLog.objects.filter(game=game).select_related("player")
    return render(request, "quiz/logs.html", {"game": game, "logs": logs})
