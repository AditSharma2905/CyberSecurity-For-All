from django.contrib import admin

from .models import AnalyticsEvent, Answer, Question, Quiz, QuizAnswer, QuizAttempt

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ["title", "question_count", "created_at"]
    readonly_fields = ["created_at"]
    search_fields = ["title"]

    def question_count(self, obj):
        return obj.questions.count()

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["text", "quiz", "order"]
    list_filter = ["quiz"]
    search_fields = ["text"]

@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ["question", "text", "is_correct"]
    list_filter = ["is_correct", "question__quiz"]
    search_fields = ["text"]

@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ["user", "quiz", "score", "completed_at"]
    list_filter = ["quiz", "completed_at"]

@admin.register(QuizAnswer)
class QuizAnswerAdmin(admin.ModelAdmin):
    list_display = ["attempt", "question", "selected_answer"]
    list_filter = ["attempt__quiz"]

@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ["event_type", "user", "ip_address", "created_at"]
    list_filter = ["event_type", "created_at"]
    search_fields = ["user__username", "ip_address"]
    readonly_fields = ["created_at"]
