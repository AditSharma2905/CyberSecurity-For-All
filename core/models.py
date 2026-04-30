from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

# --- USER PROFILE ---

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    dob = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

# --- QUIZ STRUCTURE ---

class Quiz(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Quizzes"

    def __str__(self):
        return self.title

    @property
    def question_count(self):
        return self.questions.count()

class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    explanation = models.TextField(blank=True, help_text="Shown after answering")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.text[:100]

class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="answers")
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.text} ({'✅' if self.is_correct else '❌'})"

# --- ATTEMPTS & RESULTS ---

class QuizAttempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    score = models.IntegerField(default=0)
    total_questions = models.IntegerField(default=0)
    completed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user or 'Anonymous'} - {self.score}/{self.total_questions}"

class QuizAnswer(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_answer = models.ForeignKey(Answer, on_delete=models.CASCADE)
    is_correct = models.BooleanField()

    def __str__(self):
        return f"Q{self.question.id}: {'✅' if self.is_correct else '❌'}"

# --- SIGNALS ---

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()
