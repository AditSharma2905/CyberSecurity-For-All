from django.shortcuts import render, get_object_or_404, redirect
from .hibp_client import check_breaches
from .LLM_api import LLM_API
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import Quiz, Question, Answer, QuizAttempt, QuizAnswer
import json
from django.views.decorators.http import require_http_methods


def home(request):
    return render(request, "core/home.html")
# HIBP Breach email checker view
def breach_checker(request):
    context = {}
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        context["email"] = email
        if email:
            breaches = check_breaches(email)
            context["breaches"] = breaches
        else:
            context["breaches"] = []
    return render(request, "core/breach_checker.html", context)

# Groq API question view
def chatbot(request):
    answer = None
    question = ""
    
    if request.method == "POST":
        question = request.POST.get("question", "").strip()
        if question:
            answer = LLM_API().get_llm_response(question)
            if not answer:
                answer = "Sorry, I could not get a response right now. Please try again."
    
    return render(request, "core/chatbot.html", {
        "question": question,
        "answer": answer,
    })


# Quiz Views
def quiz_list(request):
    """List all quizzes."""
    quizzes = Quiz.objects.all().order_by('-created_at')
    return render(request, "core/quiz_list.html", {"quizzes": quizzes})

def take_quiz(request, quiz_id):
    """Display quiz form."""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    questions = quiz.questions.select_related('answers').order_by('order')
    
    if request.method == 'POST':
        return process_quiz(request, quiz)
    
    return render(request, "core/take_quiz.html", {
        "quiz": quiz,
        "questions": questions
    })

def process_quiz(request, quiz):
    """Grade quiz and save results."""
    questions = list(quiz.questions.all())
    
    attempt = QuizAttempt.objects.create(
        user=request.user if request.user.is_authenticated else None,
        quiz=quiz,
        total_questions=len(questions)
    )
    
    score = 0
    for question in questions:
        answer_id = request.POST.get(f'q_{question.id}')
        if answer_id:
            try:
                answer = Answer.objects.get(id=answer_id)
                is_correct = answer.is_correct
                QuizAnswer.objects.create(
                    attempt=attempt,
                    question=question,
                    answer=answer,
                    is_correct=is_correct
                )
                if is_correct:
                    score += 1
            except Answer.DoesNotExist:
                pass
    
    attempt.score = score
    attempt.save()
    
    messages.success(request, f"You scored {score}/{len(questions)} ({score/len(questions)*100:.0f}%)!")
    return redirect('core:quiz_results', quiz_id=quiz.id, attempt_id=attempt.id)

def quiz_results(request, quiz_id, attempt_id):
    """Show results with explanations."""
    attempt = get_object_or_404(QuizAttempt, id=attempt_id)
    percentage = round(attempt.score / attempt.total_questions * 100) if attempt.total_questions else 0
    return render(request, "core/quiz_results.html", {"attempt": attempt, "percentage": percentage})


def generate_quiz(request):  # Simple function view
    if request.method == "GET":
        # Renders your form
        return render(request, "core/generate_quiz.html")
    
    # POST handling
    topic = request.POST.get("topic", "cybersecurity")
    agegroup = request.POST.get("agegroup", "all")
    
    prompt = f'Quiz on "{topic}" for {agegroup}. Return JSON only:\n{{"title":"...", "questions":[...], "description":"..."}}'
    
    response = LLM_API().get_llm_response(prompt)
    
    # Safe JSON response
    try:
        return JsonResponse({"quiz": json.loads(response)})
    except:
        return JsonResponse({"raw": response})
