# Generated migration for GeneratedMCQ model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('base', '0002_profile_delete_userprofile'),
    ]

    operations = [
        migrations.CreateModel(
            name='GeneratedMCQ',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('topic', models.CharField(choices=[('Python', 'Python'), ('Java', 'Java'), ('JavaScript', 'JavaScript'), ('SQL', 'SQL'), ('HTML_CSS', 'HTML/CSS'), ('General', 'General Knowledge')], max_length=50)),
                ('subtopic', models.CharField(max_length=100)),
                ('difficulty', models.CharField(choices=[('Easy', 'Easy'), ('Medium', 'Medium'), ('Hard', 'Hard')], max_length=10)),
                ('question_no', models.PositiveIntegerField()),
                ('question', models.TextField()),
                ('option1', models.CharField(max_length=255)),
                ('option2', models.CharField(max_length=255)),
                ('option3', models.CharField(max_length=255)),
                ('option4', models.CharField(max_length=255)),
                ('correct_answer', models.CharField(choices=[('A', 'Option A'), ('B', 'Option B'), ('C', 'Option C'), ('D', 'Option D')], max_length=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['topic', 'question_no'],
            },
        ),
    ]