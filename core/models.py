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

def compute_universal_leaderboard():
    """Return the all-time hall-of-fame as a list of dicts.

    For each authenticated user, for each quiz they've attempted,
    take their best (score * total_questions).  Sum those bests
    per user.  Order by total_points descending.
    """
    from collections import defaultdict

    from django.contrib.auth.models import User

    attempts = (
        QuizAttempt.objects
        .filter(user__isnull=False)
        .select_related("user")
        .only("user", "quiz", "score", "total_questions")
    )

    # (user_id, quiz_id) -> best points
    best_points = defaultdict(lambda: defaultdict(int))
    user_ids = set()

    for a in attempts:
        points = a.score * a.total_questions
        if points > best_points[a.user_id][a.quiz_id]:
            best_points[a.user_id][a.quiz_id] = points
        user_ids.add(a.user_id)

    if not user_ids:
        return []

    # Compute totals and sort
    totals = [
        (uid, sum(best_points[uid].values()), len(best_points[uid]))
        for uid in user_ids
    ]
    totals.sort(key=lambda t: t[1], reverse=True)

    # Fetch user display info
    user_map = {
        u.id: u
        for u in User.objects.filter(id__in=[t[0] for t in totals]).only(
            "id", "username", "first_name", "last_name"
        )
    }

    return [
        {
            "rank": rank,
            "username": (
                user_map[uid].get_full_name() or user_map[uid].username
            ) if uid in user_map else "Unknown",
            "total_points": total,
            "quizzes_completed": quiz_count,
        }
        for rank, (uid, total, quiz_count) in enumerate(totals, start=1)
    ]


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()
