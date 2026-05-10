import markdown
from collections import Counter
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.db.models import Avg, Count, F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic.edit import CreateView

from .forms import CustomSignupForm
from .hibp_client import check_breaches
from .LLM_api import LLMAPI
from .models import (
    AnalyticsEvent, Answer, Question, Quiz, QuizAnswer, QuizAttempt,
    compute_universal_leaderboard,
)


# --- HELPERS ---

def _track(request, event_type, **metadata):
    """Log an analytics event."""
    AnalyticsEvent.objects.create(
        event_type=event_type,
        user=request.user if request.user.is_authenticated else None,
        metadata=metadata or {},
        ip_address=request.META.get("REMOTE_ADDR"),
    )

# --- AUTH ---

class SignUpView(CreateView):
    form_class = CustomSignupForm
    success_url = reverse_lazy("login")
    template_name = "registration/signup.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        _track(self.request, "signup", username=form.cleaned_data["username"])
        return response

# --- PAGES ---

def home(request):
    _track(request, "page_visit", page="home")
    return render(request, "core/home.html")

def breach_checker(request):
    context = {}
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        context["email"] = email
        context["breaches"] = check_breaches(email) if email else []
        breach_count = len(context["breaches"]) if context["breaches"] else 0
        _track(request, "breach_check", breaches_found=breach_count)
    return render(request, "core/breach_checker.html", context)

def chatbot(request):
    answer = None
    question = request.POST.get("question", "").strip() if request.method == "POST" else ""

    if question:
        try:
            answer = LLMAPI().get_llm_response(question)
            if not answer:
                answer = "Sorry, I could not get a response right now. Please try again."
            else:
                answer = markdown.markdown(answer)
        except ConnectionError:
            answer = "Service unavailable. Both AI providers failed to respond. Please try again later."
        except Exception:
            answer = "An unexpected error occurred. Please try again later."

    if question:
        _track(request, "chatbot_query", topic=question[:100])
    return render(request, "core/chatbot.html", {"question": question, "answer": answer})

def universal_leaderboard(request):
    rows = compute_universal_leaderboard()
    return render(request, "core/universal_leaderboard.html", {
        "rows": rows,
        "page_size": 20
    })

# --- QUIZ MANAGEMENT ---

def quiz_list(request):
    quizzes = Quiz.objects.all().order_by("-created_at")
    return render(request, "core/quiz_list.html", {"quizzes": quizzes})

def take_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    if request.method == "POST":
        return _process_quiz_submission(request, quiz)

    questions = quiz.questions.prefetch_related("answers").order_by("order")
    return render(request, "core/take_quiz.html", {"quiz": quiz, "questions": questions})

def _process_quiz_submission(request, quiz):
    """Helper to grade and save quiz results."""
    questions = quiz.questions.all()
    attempt = QuizAttempt.objects.create(
        user=request.user if request.user.is_authenticated else None,
        quiz=quiz,
        total_questions=questions.count()
    )

    score = 0
    for question in questions:
        answer_id = request.POST.get(f"q_{question.id}")
        if answer_id:
            try:
                ans = Answer.objects.get(id=answer_id)
                QuizAnswer.objects.create(
                    attempt=attempt,
                    question=question,
                    selected_answer=ans,
                    is_correct=ans.is_correct
                )
                if ans.is_correct:
                    score += 1
            except Answer.DoesNotExist:
                continue

    attempt.score = score
    attempt.save()

    # Notify leaderboard
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"leaderboard_{quiz.id}", {"type": "leaderboard_update"}
    )

    if request.user.is_authenticated:
        current_points = attempt.score * attempt.total_questions
        previous_best = (
            QuizAttempt.objects
            .filter(user=request.user, quiz=quiz)
            .exclude(id=attempt.id)
            .annotate(points=F("score") * F("total_questions"))
            .order_by("-points")
            .values_list("points", flat=True)
            .first()
        ) or 0

        if current_points > previous_best:
            async_to_sync(channel_layer.group_send)(
                "leaderboard_universal", {"type": "leaderboard_update"}
            )

    _track(request, "quiz_complete", quiz_title=quiz.title,
           score=score, total=attempt.total_questions)
    messages.success(request, f"You scored {score}/{attempt.total_questions}!")
    return redirect("core:quiz_results", quiz_id=quiz.id, attempt_id=attempt.id)

def quiz_results(request, quiz_id, attempt_id):
    attempt = get_object_or_404(QuizAttempt, id=attempt_id)
    percentage = round(attempt.score / attempt.total_questions * 100) if attempt.total_questions else 0
    return render(request, "core/quiz_results.html", {"attempt": attempt, "percentage": percentage})

# --- GENERATION & LEADERBOARD ---

def generate_quiz(request):
    if request.method == "GET":
        return render(request, "core/generate_quiz.html")

    topic = request.POST.get("topic", "cybersecurity")
    agegroup = request.POST.get("agegroup", "all")

    try:
        quiz_data = LLMAPI().generate_quiz_data(topic, agegroup)

        with transaction.atomic():
            quiz = Quiz.objects.create(
                title=quiz_data.get("title", f"{topic} Quiz"),
                description=quiz_data.get("description", "")
            )

            for i, q in enumerate(quiz_data.get("questions", [])):
                question = Question.objects.create(
                    quiz=quiz,
                    text=q.get("text", q.get("question", "")),
                    explanation=q.get("explanation", ""),
                    order=i
                )

                for a in q.get("answers", []):
                    Answer.objects.create(
                        question=question,
                        text=a.get("text", ""),
                        is_correct=a.get("is_correct", a.get("correct", False))
                    )

        _track(request, "quiz_generate", topic=topic, agegroup=agegroup)
        return JsonResponse({"redirect_url": reverse("core:take_quiz", args=[quiz.id])})
    except Exception as e:
        return JsonResponse({"error": f"Parse error: {str(e)}"}, status=400)

def leaderboard(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    attempts = (
        QuizAttempt.objects.filter(quiz=quiz)
        .select_related("user")
        .order_by("-score", "completed_at")[:20]
    )
    rows = [
        {
            "rank": i,
            "username": a.user.get_full_name() or a.user.username if a.user else "Anonymous",
            "score": a.score,
            "total": a.total_questions,
            "percentage": round(a.score / a.total_questions * 100) if a.total_questions else 0,
            "completed_at": a.completed_at.strftime("%H:%M:%S"),
        }
        for i, a in enumerate(attempts, start=1)
    ]
    return render(request, "core/leaderboard.html", {"quiz": quiz, "rows": rows})

# --- ANALYTICS ---

@staff_member_required
def analytics(request):
    now = timezone.now()
    week_ago = now - timedelta(days=7)

    all_events = AnalyticsEvent.objects.all()
    recent_events = all_events.filter(created_at__gte=week_ago)

    # Aggregate counts by event type (all time)
    type_counts = dict(
        all_events.values_list("event_type")
        .annotate(count=Count("id"))
        .values_list("event_type", "count")
    )

    # Recent counts (last 7 days)
    recent_type_counts = dict(
        recent_events.values_list("event_type")
        .annotate(count=Count("id"))
        .values_list("event_type", "count")
    )

    # Daily activity for the last 7 days
    daily_activity = []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).date()
        count = all_events.filter(
            created_at__date=day
        ).count()
        daily_activity.append({"date": day.strftime("%a %d %b"), "count": count})

    # Popular quiz topics (from quiz_complete + quiz_generate metadata)
    quiz_events = all_events.filter(
        event_type__in=["quiz_complete", "quiz_generate"]
    )
    topic_counter = Counter()
    for evt in quiz_events:
        title = evt.metadata.get("quiz_title") or evt.metadata.get("topic", "Unknown")
        topic_counter[title] += 1
    popular_topics = topic_counter.most_common(10)

    # Average quiz score
    score_events = all_events.filter(event_type="quiz_complete")
    total_score_sum = 0
    total_score_count = 0
    for evt in score_events:
        s = evt.metadata.get("score")
        t = evt.metadata.get("total")
        if s is not None and t:
            total_score_sum += (s / t) * 100
            total_score_count += 1
    avg_score = round(total_score_sum / total_score_count) if total_score_count else 0

    # Recent chatbot queries
    recent_queries = (
        all_events.filter(event_type="chatbot_query")
        .order_by("-created_at")[:10]
    )

    # User count
    from django.contrib.auth.models import User
    total_users = User.objects.count()

    context = {
        "total_users": total_users,
        "total_events": all_events.count(),
        "type_counts": type_counts,
        "recent_type_counts": recent_type_counts,
        "daily_activity": daily_activity,
        "popular_topics": popular_topics,
        "avg_score": avg_score,
        "recent_queries": recent_queries,
    }
    return render(request, "core/analytics.html", context)
