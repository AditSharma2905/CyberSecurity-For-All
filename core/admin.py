from django.contrib import admin
from .models import Quiz, Question, Answer, QuizAttempt, QuizAnswer

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ['title', 'question_count', 'created_at']
    readonly_fields = ['created_at']

    def question_count(self, obj):
        return obj.questions.count()

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['text', 'quiz', 'order']
    list_filter = ['quiz']

@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ['question', 'text', 'is_correct']
    list_filter = ['question__quiz', 'is_correct']

admin.site.register(QuizAttempt)
admin.site.register(QuizAnswer)
