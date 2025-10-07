# Generated manually for gamification features

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('base', '0014_alter_quizattempt_time_taken'),
    ]

    operations = [
        migrations.RunSQL(
            "DROP TABLE IF EXISTS base_achievement;",
            reverse_sql="CREATE TABLE base_achievement (id INT AUTO_INCREMENT PRIMARY KEY);"
        ),
        migrations.CreateModel(
            name='Achievement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='Default Achievement', max_length=100)),
                ('description', models.TextField(default='Achievement description')),
                ('icon', models.CharField(default='🏆', max_length=10)),
                ('achievement_type', models.CharField(choices=[('streak', 'Streak'), ('accuracy', 'Accuracy'), ('completion', 'Completion'), ('topic_master', 'Topic Master')], default='completion', max_length=20)),
                ('requirement', models.IntegerField(default=1)),
                ('xp_reward', models.IntegerField(default=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='UserXP',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_xp', models.IntegerField(default=0)),
                ('level', models.IntegerField(default=1)),
                ('current_streak', models.IntegerField(default=0)),
                ('longest_streak', models.IntegerField(default=0)),
                ('last_quiz_date', models.DateField(blank=True, null=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='UserAchievement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('earned_at', models.DateTimeField(auto_now_add=True)),
                ('achievement', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='base.achievement')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('user', 'achievement')},
            },
        ),
    ]