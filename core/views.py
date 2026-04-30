from django.shortcuts import render, get_object_or_404, redirect
from .hibp_client import check_breaches
from .LLM_api import LLM_API
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone
from .models import Quiz, Question, Answer, QuizAttempt, QuizAnswer
import json
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.urls import reverse


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
    
    # Use prefetch_related for reverse foreign key relationships
    questions = quiz.questions.prefetch_related('answers').order_by('order') # type: ignore
    
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

    # Send live leaderboard update
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"leaderboard_{quiz.id}",
        {
            "type": "leaderboard_update",
        }
    )
    
    messages.success(request, f"You scored {score}/{len(questions)} ({score/len(questions)*100:.0f}%)!")
    return redirect('core:quiz_results', quiz_id=quiz.id, attempt_id=attempt.id)

def quiz_results(request, quiz_id, attempt_id):
    """Show results with explanations."""
    attempt = get_object_or_404(QuizAttempt, id=attempt_id)
    percentage = round(attempt.score / attempt.total_questions * 100) if attempt.total_questions else 0
    return render(request, "core/quiz_results.html", {"attempt": attempt, "percentage": percentage})


def generate_quiz(request):
    if request.method == "GET":
        return render(request, "core/generate_quiz.html")
    
    topic = request.POST.get("topic", "cybersecurity")
    agegroup = request.POST.get("agegroup", "all")
    
    prompt = f'Quiz on "{topic}" for {agegroup}. Return JSON only without markdown formatting:\n{{"title":"...", "description":"...", "questions":[{{"text":"...", "explanation":"...", "answers":[{{"text":"...", "is_correct":true}}]}}]}}'
    
    response = LLM_API().get_llm_response(prompt)
    
    try:
        # Extract only the JSON portion from the LLM's response
        start_idx = response.find('{')
        end_idx = response.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            clean_response = response[start_idx:end_idx+1]
        else:
            clean_response = response
            
        quiz_data = json.loads(clean_response)
        
        # Use a database transaction so it only saves if everything is successful
        with transaction.atomic():
            quiz = Quiz.objects.create(
                title=quiz_data.get("title", f"{topic} Quiz"),
                description=quiz_data.get("description", "")
            )
            
            for i, q_data in enumerate(quiz_data.get("questions", [])):
                question = Question.objects.create(
                    quiz=quiz,
                    text=q_data.get("text", q_data.get("question", "")),
                    explanation=q_data.get("explanation", ""),
                    order=i
                )
                
                for a_data in q_data.get("answers", []):
                    Answer.objects.create(
                        question=question,
                        text=a_data.get("text", ""),
                        is_correct=a_data.get("is_correct", a_data.get("correct", False)) 
                    )
                    
        return JsonResponse({"redirect_url": reverse("core:take_quiz", args=[quiz.id])})
        
    except Exception as e:
        return JsonResponse({"error": f"Failed to parse and save quiz: {str(e)} \n\nRaw Output: {response}"})