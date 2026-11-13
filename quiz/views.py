import re

from django.db.models import Count
from django.db.models.deletion import ProtectedError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Game, GameLog, Question, TEACHER_QUIZ_CATEGORY
from .forms import QuestionForm


def home(request):
    return render(request, "quiz/home.html", home_context())


def home_context():
    active_questions = Question.objects.filter(is_active=True)
    categories = list(active_questions.exclude(category="").order_by(
        "category").values_list("category", flat=True).distinct())
    question_stats = list(active_questions.values("category").annotate(count=Count("id")))
    return {"categories": categories, "question_stats": question_stats, "join_error": ""}


def join_response(request, code):
    """参加コードを検証してプレイヤー画面へ。無効ならホームにエラー表示して戻す。"""
    code = re.sub(r"\D", "", code or "")
    game = Game.objects.filter(join_code=code).first() if code else None
    if not game:
        return home_with_join_error(request, "そのコードのゲームは見つかりません。コードを確認してください。")
    if game.status == Game.Status.FINISHED:
        return home_with_join_error(request, "このゲームは終了しました。司会が次のゲームを準備するのをお待ちください。")
    return redirect("quiz:player", game_id=game.id)


def home_with_join_error(request, message):
    context = home_context()
    context["join_error"] = message
    return render(request, "quiz/home.html", context, status=400)


@require_POST
def join(request):
    return join_response(request, request.POST.get("code", ""))


def join_by_code(request, code):
    """/j/1234/ 形式のショートカット。"""
    return join_response(request, code)


@require_POST
def new_game(request):
    title = request.POST.get("title", "文化祭クイズ").strip()[:100] or "文化祭クイズ"
    try:
        minutes = max(
            1, min(int(request.POST.get("minutes", request.POST.get("seconds", 5))), 120))
        legacy_seconds = max(
            5, min(int(request.POST.get("seconds", minutes * 60)), 120))
    except (TypeError, ValueError):
        minutes, legacy_seconds = 5, 120
    selected_categories = [category for category in request.POST.getlist(
        "categories") if category in Question.objects.filter(is_active=True).values_list("category", flat=True)]
    game = Game.objects.create(title=title, question_count=1, seconds_per_question=legacy_seconds,
                               total_seconds=minutes * 60, selected_categories=selected_categories,
                               join_code=Game.generate_join_code())
    category_label = "・".join(
        selected_categories) if selected_categories else "全カテゴリ（先生クイズを除く）"
    GameLog.objects.create(game=game, event="game_created",
                           message=f"ゲームを作成しました（カテゴリ：{category_label}）。")
    return redirect(f"{reverse('quiz:control', kwargs={'game_id': game.id})}?key={game.admin_token}")


def game_or_404(game_id):
    return get_object_or_404(Game, id=game_id)


def control(request, game_id):
    game = admin_game_or_404(request, game_id)
    return render(request, "quiz/control.html", {"game": game, "game_minutes": max(1, game.total_seconds // 60), "player_url": request.build_absolute_uri(reverse("quiz:player", kwargs={"game_id": game.id}))})


def edit_game_mode(request, game_id):
    """参加受付中のゲームだけ、最初の設定画面と同じ見た目で出題条件を変更する。"""
    game = admin_game_or_404(request, game_id)
    if game.status != Game.Status.LOBBY or game.phase != Game.Phase.LOBBY:
        raise Http404("ゲームモードは参加受付中にだけ変更できます。")

    active_questions = Question.objects.filter(is_active=True)
    categories = list(
        active_questions.exclude(category="").order_by("category")
        .values_list("category", flat=True).distinct()
    )
    error = ""
    if request.method == "POST":
        selected_categories = list(dict.fromkeys(
            category for category in request.POST.getlist("categories") if category in categories
        ))
        eligible = (
            active_questions.filter(category__in=selected_categories)
            if selected_categories
            else active_questions.exclude(category=TEACHER_QUIZ_CATEGORY)
        )
        if not error and not eligible.exists():
            error = "そのカテゴリに一致する有効な問題がありません。"
        if not error:
            game.selected_categories = selected_categories
            game.save(update_fields=["selected_categories"])
            category_label = "・".join(
                selected_categories) if selected_categories else "全カテゴリ（先生クイズを除く）"
            GameLog.objects.create(game=game, event="question_options_changed",
                                   message=f"出題設定を変更しました（カテゴリ：{category_label}）。")
            return redirect(f"{reverse('quiz:control', kwargs={'game_id': game.id})}?key={game.admin_token}")

    return render(request, "quiz/game_mode.html", {
        "game": game,
        "categories": categories,
        "error": error,
    })


def display(request, game_id):
    return render(request, "quiz/display.html", {"game": game_or_404(game_id)})


def ranking(request, game_id):
    return render(request, "quiz/ranking.html", {"game": game_or_404(game_id)})


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
        form = QuestionForm(request.POST, request.FILES,
                            instance=editing_question)
        if form.is_valid():
            form.save()
            return redirect(f"{reverse('quiz:question_manager', kwargs={'game_id': game.id})}?key={game.admin_token}")
    else:
        form = QuestionForm(instance=editing_question, initial=None if editing_question else {
                            "points": 10, "is_active": True})
    questions = Question.objects.annotate(
        game_count=Count("gamequestion")).order_by("-created_at")
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
    questions = Question.objects.annotate(
        game_count=Count("gamequestion")).order_by("-created_at")
    return render(request, "quiz/question_manager.html", {"game": game, "form": form, "questions": questions, "manager_error": error})


def game_logs(request, game_id):
    game = admin_game_or_404(request, game_id)
    logs = GameLog.objects.filter(game=game).select_related("player")
    return render(request, "quiz/logs.html", {"game": game, "logs": logs})
