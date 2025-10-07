from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Avg, Q


# Create your models here.
class Profile(models.Model):
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    username = models.CharField(max_length=15, blank=True)
    mail = models.EmailField(max_length=254, blank=True)
    contact = models.CharField(max_length=15, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)

    def __str__(self):
        return self.user.username

# This code automatically creates a Profile when a User is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.profile.save()
    except:
        pass

@receiver(post_save, sender=User)
def create_user_preferences(sender, instance, created, **kwargs):
    if created:
        UserPreferences.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_preferences(sender, instance, **kwargs):
    try:
        if hasattr(instance, 'userpreferences'):
            instance.userpreferences.save()
    except:
        pass

class PDFUpload(models.Model):

    # Difficulty level choices
    DIFFICULTY_CHOICES = [
        ('Easy', 'Easy'),
        ('Medium', 'Medium'),
        ('Hard', 'Hard'),
    ]
    
    # Topic categories (you can customize these)
    TOPIC_CHOICES = [
        ('Python', 'Python'),
        ('Java', 'Java'),
        ('JavaScript', 'JavaScript'),
        ('SQL', 'SQL'),
        ('HTML_CSS', 'HTML/CSS'),
        ('General', 'General Knowledge'),
    ]
    
    # Model fields
    topic = models.CharField(max_length=50, choices=TOPIC_CHOICES)
    subtopic = models.CharField(max_length=100)  # More specific category
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES)
    question_no = models.PositiveIntegerField()  # Question number in the PDF
    question = models.TextField()
    option1 = models.CharField(max_length=255)
    option2 = models.CharField(max_length=255)
    option3 = models.CharField(max_length=255)
    option4 = models.CharField(max_length=255)
    # Fixed correct_answer to match utils.py extraction (A-D)
    correct_answer = models.CharField(max_length=1, choices=[
        ('A', 'Option A'),
        ('B', 'Option B'),
        ('C', 'Option C'),
        ('D', 'Option D'),
    ])
    uploaded_at = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.topic} - Q{self.question_no}: {self.question[:30]}..."
    
    class Meta:
        ordering = ['topic', 'question_no']

class QuizAttempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    score = models.FloatField()  # Score as decimal (0.0 to 1.0)
    attempt_date = models.DateField(auto_now_add=True)
    topic = models.CharField(max_length=100)
    subtopic = models.CharField(max_length=100, blank=True)
    correct_answers = models.PositiveIntegerField(default=0)
    wrong_answers = models.PositiveIntegerField(default=0)
    total_questions = models.PositiveIntegerField(default=0)
    time_taken = models.FloatField(default=0.0)  # Time in minutes
    difficulty = models.CharField(max_length=10, blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.topic} - {self.score}"

class UserPreferences(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    default_questions = models.PositiveIntegerField(default=10)
    preferred_difficulty = models.CharField(max_length=10, blank=True)
    enable_timer = models.BooleanField(default=True)
    show_answers = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)
    achievement_notifications = models.BooleanField(default=True)
    weekly_reports = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.user.username} - Preferences"

class AIGeneratedPDF(models.Model):
    DIFFICULTY_CHOICES = [
        ('Easy', 'Easy'),
        ('Medium', 'Medium'),
        ('Hard', 'Hard'),
    ]
    
    topic = models.CharField(max_length=100)
    subtopic = models.CharField(max_length=100)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES)
    num_questions = models.PositiveIntegerField()
    pdf_file = models.FileField(upload_to='ai_generated_pdfs/')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    def __str__(self):
        return f"{self.topic} - {self.subtopic} ({self.num_questions} questions)"
    
    class Meta:
        ordering = ['-created_at']

class GeneratedMCQ(models.Model):
    DIFFICULTY_CHOICES = [
        ('Easy', 'Easy'),
        ('Medium', 'Medium'),
        ('Hard', 'Hard'),
    ]
    
    TOPIC_CHOICES = [
        ('Python', 'Python'),
        ('Java', 'Java'),
        ('JavaScript', 'JavaScript'),
        ('SQL', 'SQL'),
        ('HTML_CSS', 'HTML/CSS'),
        ('General', 'General Knowledge'),
    ]
    
    topic = models.CharField(max_length=50, choices=TOPIC_CHOICES)
    subtopic = models.CharField(max_length=100)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES)
    question_no = models.PositiveIntegerField()
    question = models.TextField()
    option1 = models.CharField(max_length=255)
    option2 = models.CharField(max_length=255)
    option3 = models.CharField(max_length=255)
    option4 = models.CharField(max_length=255)
    correct_answer = models.CharField(max_length=1, choices=[
        ('A', 'Option A'),
        ('B', 'Option B'),
        ('C', 'Option C'),
        ('D', 'Option D'),
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    def __str__(self):
        return f"{self.topic} - Q{self.question_no}: {self.question[:30]}..."
    
    class Meta:
        ordering = ['topic', 'question_no']

class Achievement(models.Model):
    ACHIEVEMENT_TYPES = [
        ('streak', 'Streak'),
        ('accuracy', 'Accuracy'),
        ('completion', 'Completion'),
        ('topic_master', 'Topic Master'),
    ]
    
    name = models.CharField(max_length=100, default='Default Achievement')
    description = models.TextField(default='Achievement description')
    icon = models.CharField(max_length=10, default='🏆')
    achievement_type = models.CharField(max_length=20, choices=ACHIEVEMENT_TYPES, default='completion')
    requirement = models.IntegerField(default=1)
    xp_reward = models.IntegerField(default=50)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class UserAchievement(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'achievement']

class UserXP(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    total_xp = models.IntegerField(default=0)
    level = models.IntegerField(default=1)
    current_streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    last_quiz_date = models.DateField(null=True, blank=True)
    
    def add_xp(self, points):
        self.total_xp += points
        self.level = (self.total_xp // 100) + 1
        self.save()
    
    def update_streak(self):
        today = timezone.now().date()
        if self.last_quiz_date:
            if self.last_quiz_date == today:
                return
            elif self.last_quiz_date == today - timedelta(days=1):
                self.current_streak += 1
            else:
                self.current_streak = 1
        else:
            self.current_streak = 1
        
        if self.current_streak > self.longest_streak:
            self.longest_streak = self.current_streak
        
        self.last_quiz_date = today
        self.save()

def check_achievements(user):
    """Check and award achievements for user"""
    user_xp, created = UserXP.objects.get_or_create(user=user)
    achievements_earned = []
    
    total_quizzes = QuizAttempt.objects.filter(user=user).count()
    avg_score = QuizAttempt.objects.filter(user=user).aggregate(avg=Avg('score'))['avg'] or 0
    
    achievements_to_check = [
        ('🔥', 'Streak Master', 'Complete quizzes for 7 days straight', 'streak', 7),
        ('🎯', 'Sharp Shooter', 'Achieve 90%+ average score', 'accuracy', 90),
        ('🏆', 'Quiz Champion', 'Complete 10 quizzes', 'completion', 10),
        ('💯', 'Perfect Score', 'Get 100% on any quiz', 'accuracy', 100),
    ]
    
    for icon, name, desc, type_, req in achievements_to_check:
        achievement, created = Achievement.objects.get_or_create(
            name=name,
            defaults={
                'description': desc,
                'icon': icon,
                'achievement_type': type_,
                'requirement': req
            }
        )
        
        earned = False
        if type_ == 'streak' and user_xp.current_streak >= req:
            earned = True
        elif type_ == 'accuracy' and avg_score >= req:
            earned = True
        elif type_ == 'completion' and total_quizzes >= req:
            earned = True
        
        if earned:
            user_achievement, created = UserAchievement.objects.get_or_create(
                user=user, achievement=achievement
            )
            if created:
                user_xp.add_xp(achievement.xp_reward)
                achievements_earned.append(achievement)
    
    return achievements_earned

class TopicRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected')
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    topic = models.CharField(max_length=100)
    subtopic = models.CharField(max_length=100, blank=True)
    difficulty = models.CharField(max_length=20, choices=[('Easy', 'Easy'), ('Medium', 'Medium'), ('Hard', 'Hard')])
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.topic} - {self.subtopic} ({self.status})"

class LearningPathProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    path_name = models.CharField(max_length=100)
    current_module = models.IntegerField(default=0)
    current_topic = models.CharField(max_length=100)
    completed_modules = models.JSONField(default=list)
    started_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'path_name']
    
    def __str__(self):
        return f"{self.user.username} - {self.path_name}"
    
