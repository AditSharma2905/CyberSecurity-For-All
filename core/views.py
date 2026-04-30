import json

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic.edit import CreateView

from .forms import CustomSignupForm
from .hibp_client import check_breaches
from .LLM_api import LLMAPI
from .models import Answer, Question, Quiz, QuizAnswer, QuizAttempt

# --- AUTH ---

class SignUpView(CreateView):
    form_class = CustomSignupForm
    success_url = reverse_lazy("login")
    template_name = "registration/signup.html"

# --- PAGES ---

def home(request):
    return render(request, "core/home.html")

def breach_checker(request):
    context = {}
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        context["email"] = email
        context["breaches"] = check_breaches(email) if email else []
    return render(request, "core/breach_checker.html", context)

def chatbot(request):
    answer = None
    question = request.POST.get("question", "").strip() if request.method == "POST" else ""

    if question:
        answer = LLMAPI().get_llm_response(question)
        if not answer:
            answer = "Sorry, I could not get a response right now. Please try again."

    return render(request, "core/chatbot.html", {"question": question, "answer": answer})

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
