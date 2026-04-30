from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("breach-checker/", views.breach_checker, name="breach_checker"),
    path("chatbot/", views.chatbot, name="chatbot"),
    
    path("quizzes/", views.quiz_list, name="quiz_list"),
    path("take-quiz/<int:quiz_id>/", views.take_quiz, name="take_quiz"),
    path("results/<int:quiz_id>/<int:attempt_id>/", views.quiz_results, name="quiz_results"),
    
    path("generate-quiz/", views.generate_quiz, name="generate_quiz"),
    
    path("signup/", views.SignUpView.as_view(), name="signup"),
    path("leaderboard/<int:quiz_id>/", views.leaderboard, name="leaderboard")
]