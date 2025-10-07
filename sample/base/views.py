from datetime import timedelta
import random
import json
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db.models import Avg, Count, Q, Max
from django.db.models.functions import TruncMonth
from .models import PDFUpload, QuizAttempt, GeneratedMCQ, AIGeneratedPDF
from .ai_suggestions import get_ai_suggestions
from .utils import extract_mcqs_from_pdf
from .ai_quiz_generator import AIQuizGenerator

# Create your views here.
def home(request):
    return render(request,'home.html')

def admin_login(request):
    # If user is already authenticated and is staff, redirect to admin dashboard
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        return redirect('admindashboard')
    
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        if not username or not password:
            messages.error(request, "Username and password are required")
            return redirect('adminlogin')

        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Check if user has admin privileges BEFORE logging them in
            if user.is_staff or user.is_superuser:
                auth_login(request, user)
                messages.success(request, f"Welcome Admin {user.username}!")
                return redirect('admindashboard')
            else:
                # User exists but doesn't have admin privileges
                messages.error(request, "You do not have administrator privileges.")
                return redirect('adminlogin')
        else:
            messages.error(request, "Invalid username or password")
            return redirect('adminlogin')

    return render(request, 'admin.html')

def user_login(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        if not username or not password:
            messages.error(request, "Username and password are required")
            return redirect('login')

        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            auth_login(request, user)
            messages.success(request, f"Welcome {user.username}!")
            
            # Redirect to appropriate dashboard based on user type
            if user.is_staff or user.is_superuser:
                return redirect('admindashboard')
            else:
                return redirect('userdashboard')
        else:
            messages.error(request, "Invalid username or password")
            return redirect('login')

    return render(request, 'login.html')

def register(request):
    if request.method == "POST":
        username = request.POST.get('username')
        first_name = request.POST.get('firstname')
        last_name = request.POST.get('lastname')
        email = request.POST.get('mail')
        password = request.POST.get('password')
        cpassword = request.POST.get('cpassword')
        
        if not all([username, first_name, last_name, email, password, cpassword]):
            messages.error(request, "All fields are required")
            return render(request, 'register.html')
        # Get additional fields for profile
        contact = request.POST.get('contact', '')
        gender = request.POST.get('gender', '')

        if password != cpassword:
            messages.error(request, "Passwords do not match")
            return render(request, 'register.html')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered. Please login.")
            return redirect('login')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken. Please choose another.")
            return render(request, 'register.html')

        # Create the user (email is saved here)
        user = User.objects.create_user(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,  # Email saved to User model
            password=password
        )
        
        # Save additional profile data (NOT email)
        profile = user.profile
        if contact:
            profile.contact = contact
        if gender:
            profile.gender = gender
        profile.save()
        
        messages.success(request, "Registration successful! Please login.")
        return redirect('login')

    return render(request, 'register.html')

@login_required
def admindashboard(request):
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "You are not authorized to view this page.")
        return redirect('home')
    
    today = timezone.now().date()
    total_users = User.objects.count()
    total_questions = PDFUpload.objects.count() + GeneratedMCQ.objects.count()
    quizzes_today = QuizAttempt.objects.filter(attempt_date=today).count()
    avg_score = QuizAttempt.objects.aggregate(avg_score=Avg('score'))['avg_score'] or 0
    avg_score_percentage = round(avg_score, 1) if avg_score else 0
    
    recent_users = User.objects.all().order_by('-date_joined')[:5]
    for user in recent_users:
        user.quiz_count = QuizAttempt.objects.filter(user=user).count()
    
    # User growth data - Week, Month, Year
    from datetime import timedelta
    now = timezone.now()
    
    # Weekly data
    week_data = []
    for i in range(7):
        day = now - timedelta(days=6-i)
        count = User.objects.filter(date_joined__date=day.date()).count()
        week_data.append(count)
    
    # Monthly data
    month_data = []
    for i in range(12):
        month_start = now.replace(day=1) - timedelta(days=30*i)
        month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        count = User.objects.filter(date_joined__date__range=[month_start.date(), month_end.date()]).count()
        month_data.insert(0, count)
    
    # Yearly data
    year_data = []
    for i in range(5):
        year = now.year - 4 + i
        count = User.objects.filter(date_joined__year=year).count()
        year_data.append(count)
    
    context = {
        'total_users': total_users, 'quizzes_today': quizzes_today, 'avg_score': avg_score_percentage,
        'recent_users': recent_users, 'total_questions': total_questions,
        'week_data': week_data, 'month_data': month_data, 'year_data': year_data,
    }
    return render(request,'admindashboard.html', context)

@login_required
def generate_ai_quiz(request):
    if request.method == "POST":
        if not request.user.is_staff and not request.user.is_superuser:
            return JsonResponse({'success': False, 'error': 'Not authorized'})
        
        topic = request.POST.get("topic")
        subtopic = request.POST.get("subtopic")
        difficulty = request.POST.get("difficulty")
        num_questions = int(request.POST.get("num_questions", 10))
        
        if not all([topic, subtopic, difficulty]):
            return JsonResponse({'success': False, 'error': 'All fields required'})
        
        print(f"DEBUG: Received - Topic: {topic}, Subtopic: {subtopic}, Difficulty: {difficulty}, Num: {num_questions}")
        
        try:
            print(f"DEBUG: Starting AI generation for {topic} - {subtopic}")
            generator = AIQuizGenerator()
            questions = generator.generate_quiz_content(topic, subtopic, difficulty, num_questions)
            
            if not questions:
                print("DEBUG: No questions generated")
                return JsonResponse({'success': False, 'error': 'Failed to generate questions - AI returned empty response'})
            
            print(f"DEBUG: Generated {len(questions)} questions")
            
            # Create PDF
            import os
            from django.conf import settings
            
            filename = f"{topic}_{subtopic}_{difficulty}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            pdf_path = os.path.join(settings.MEDIA_ROOT, 'ai_generated_pdfs', filename)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
            print(f"DEBUG: Creating PDF at {pdf_path}")
            
            generator.create_pdf(questions, topic, subtopic, difficulty, pdf_path)
            print("DEBUG: PDF created successfully")
            
            # Save to database
            ai_pdf = AIGeneratedPDF.objects.create(
                topic=topic,
                subtopic=subtopic,
                difficulty=difficulty,
                num_questions=num_questions,
                pdf_file=f'ai_generated_pdfs/{filename}',
                created_by=request.user
            )
            print(f"DEBUG: Saved AIGeneratedPDF with ID {ai_pdf.id}")
            
            # Save questions to GeneratedMCQ
            for idx, q in enumerate(questions, 1):
                print(f"DEBUG: Processing question {idx}: {q}")
                GeneratedMCQ.objects.create(
                    topic=topic,
                    subtopic=subtopic,
                    difficulty=difficulty,
                    question_no=idx,
                    question=q['question'],
                    option1=q['options'][0][3:] if len(q['options'][0]) > 3 else q['options'][0],
                    option2=q['options'][1][3:] if len(q['options'][1]) > 3 else q['options'][1],
                    option3=q['options'][2][3:] if len(q['options'][2]) > 3 else q['options'][2],
                    option4=q['options'][3][3:] if len(q['options'][3]) > 3 else q['options'][3],
                    correct_answer=q['correct_answer'],
                    created_by=request.user
                )
            
            print("DEBUG: All questions saved to database")
            return JsonResponse({
                'success': True, 
                'message': f'Generated {len(questions)} questions and saved PDF',
                'pdf_id': ai_pdf.id
            })
            
        except Exception as e:
            print(f"ERROR in generate_ai_quiz: {e}")
            print(f"ERROR type: {type(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': f'Error: {str(e)}'})
    
    return redirect('admindashboard')

@login_required
def view_ai_pdfs(request):
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "You are not authorized to view this page.")
        return redirect('home')
    
    ai_pdfs = AIGeneratedPDF.objects.all().order_by('-created_at')
    return render(request, 'ai_pdfs.html', {'ai_pdfs': ai_pdfs})

@login_required
def view_admin_pdfs(request):
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "You are not authorized to view this page.")
        return redirect('home')
    
    # Get aggregated data from GeneratedMCQ (admin uploaded PDFs)
    from django.db.models import Count, Max
    pdf_data = GeneratedMCQ.objects.values('topic', 'subtopic', 'difficulty').annotate(
        question_count=Count('id'),
        latest_date=Max('created_at')
    ).order_by('-latest_date')
    
    total_questions = GeneratedMCQ.objects.count()
    unique_topics = GeneratedMCQ.objects.values('topic').distinct().count()
    total_pdfs = pdf_data.count()
    
    context = {
        'pdf_data': pdf_data,
        'total_questions': total_questions,
        'unique_topics': unique_topics,
        'total_pdfs': total_pdfs,
    }
    return render(request, 'admin_pdfs.html', context)

@login_required
def view_questions(request, topic, subtopic):
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "You are not authorized to view this page.")
        return redirect('home')
    
    questions = GeneratedMCQ.objects.filter(topic=topic, subtopic=subtopic).order_by('question_no')
    context = {
        'questions': questions,
        'topic': topic,
        'subtopic': subtopic,
    }
    return render(request, 'view_questions.html', context)

@login_required
def export_admin_pdf(request, topic, subtopic):
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "You are not authorized to view this page.")
        return redirect('home')
    
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from django.http import HttpResponse
    import io
    
    questions = GeneratedMCQ.objects.filter(topic=topic, subtopic=subtopic).order_by('question_no')
    
    if not questions:
        messages.error(request, "No questions found for this topic.")
        return redirect('view_admin_pdfs')
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=1
    )
    
    title = Paragraph(f"{topic} - {subtopic} Quiz", title_style)
    story.append(title)
    story.append(Spacer(1, 20))
    
    # Questions
    for q in questions:
        question_style = ParagraphStyle(
            'Question',
            parent=styles['Normal'],
            fontSize=12,
            spaceAfter=10,
            fontName='Helvetica-Bold'
        )
        
        question_text = Paragraph(f"Q{q.question_no}. {q.question}", question_style)
        story.append(question_text)
        
        # Options
        options = [f"A) {q.option1}", f"B) {q.option2}", f"C) {q.option3}", f"D) {q.option4}"]
        for option in options:
            option_para = Paragraph(f"   {option}", styles['Normal'])
            story.append(option_para)
        
        story.append(Spacer(1, 15))
    
    # Answer key
    story.append(Spacer(1, 30))
    answer_title = Paragraph("Answer Key:", styles['Heading2'])
    story.append(answer_title)
    
    for q in questions:
        answer_text = Paragraph(f"Q{q.question_no}: {q.correct_answer}", styles['Normal'])
        story.append(answer_text)
    
    doc.build(story)
    buffer.seek(0)
    
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{topic}_{subtopic}_quiz.pdf"'
    return response

def upload_mcq(request):
    if request.method == "POST":
        topic = request.POST.get("topic")
        subtopic = request.POST.get("subtopic")
        difficulty = request.POST.get("difficulty")
        mode = request.POST.get("mode")
        
        if not request.user.is_staff and not request.user.is_superuser:
            return JsonResponse({'success': False, 'error': 'Not authorized'})
        
        if not all([topic, subtopic, difficulty, mode]):
            return JsonResponse({'success': False, 'error': 'All fields required'})
        
        try:
            if mode == 'pdf':
                pdf_file = request.FILES.get("pdf")
                if not pdf_file:
                    return JsonResponse({'success': False, 'error': 'PDF file required'})
                
                mcqs = extract_mcqs_from_pdf(pdf_file)
                extracted_count = len(mcqs)
                
                # Remove duplicates
                unique_mcqs = []
                seen_questions = set()
                duplicate_count = 0
                
                for mcq in mcqs:
                    question_text = mcq.get('question', '').strip().lower()
                    correct_ans = mcq.get('correct_answer', '').upper()
                    question_key = f"{question_text}_{correct_ans}"
                    
                    if question_key not in seen_questions:
                        unique_mcqs.append(mcq)
                        seen_questions.add(question_key)
                    else:
                        duplicate_count += 1
                
                # Save to database with duplicate check
                saved_count = 0
                skipped_count = 0
                
                for idx, mcq in enumerate(unique_mcqs, 1):
                    existing = GeneratedMCQ.objects.filter(
                        question=mcq.get("question", ""),
                        correct_answer=mcq.get("correct_answer", "A").upper()
                    ).exists()
                    
                    if existing:
                        skipped_count += 1
                        continue
                    
                    GeneratedMCQ.objects.create(
                        topic=topic,
                        subtopic=subtopic,
                        difficulty=difficulty,
                        question_no=idx,
                        question=mcq["question"],
                        option1=mcq["option_a"],
                        option2=mcq["option_b"],
                        option3=mcq["option_c"],
                        option4=mcq["option_d"],
                        correct_answer=mcq["correct_answer"].upper(),
                        created_by=request.user
                    )
                    saved_count += 1
                
                message = f'Extracted: {extracted_count} | Duplicates: {duplicate_count} | Already in DB: {skipped_count} | New saved: {saved_count}'
                return JsonResponse({'success': True, 'message': message})
                
            elif mode == 'ai':
                pdf_file = request.FILES.get("pdf")
                if not pdf_file:
                    return JsonResponse({'success': False, 'error': 'PDF file required for AI generation'})
                
                from .ml_utils import generate_mcqs
                import PyPDF2
                
                # Extract text from PDF
                pdf_file.seek(0)
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                text = "".join([page.extract_text() for page in pdf_reader.pages])
                
                if not text.strip():
                    return JsonResponse({'success': False, 'error': 'No text found in PDF'})
                
                mcqs = generate_mcqs(text, 10)
                
                # Save directly without duplicate check (AI generates unique questions)
                for idx, mcq in enumerate(mcqs, 1):
                    GeneratedMCQ.objects.create(
                        topic=topic,
                        subtopic=subtopic,
                        difficulty=difficulty,
                        question_no=idx,
                        question=mcq.get("question", ""),
                        option1=mcq.get("option_a", ""),
                        option2=mcq.get("option_b", ""),
                        option3=mcq.get("option_c", ""),
                        option4=mcq.get("option_d", ""),
                        correct_answer=mcq.get("correct_answer", "A").upper(),
                        created_by=request.user
                    )
                
                message = f'Successfully generated and saved {len(mcqs)} AI MCQs'
                return JsonResponse({'success': True, 'message': message})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return redirect('admindashboard')

def user_logout(request):
    auth_logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('home')

@login_required
def userdashboard(request):
    if not request.user.is_authenticated:
        messages.error(request, 'You need to login!')
        return redirect('login')
    
    from django.core.cache import cache
    user = request.user
    cache_key = f'dashboard_data_{user.id}'
    
    # Check if cached data exists and is recent
    cached_data = cache.get(cache_key)
    if cached_data:
        return render(request, 'userdashboard.html', cached_data)
    
    # Calculate stats
    quizzes_completed = QuizAttempt.objects.filter(user=user).count()
    avg_score_result = QuizAttempt.objects.filter(user=user).aggregate(avg_score=Avg('score'))
    avg_score = round(avg_score_result['avg_score'], 1) if avg_score_result['avg_score'] else 0
    current_streak = calculate_streak(user)
    recent_activity = QuizAttempt.objects.filter(user=user).order_by('-attempt_date')[:5]
    quiz_history_summary = QuizAttempt.objects.filter(user=user).values('topic', 'subtopic').annotate(
        count=Count('id'), avg_score=Avg('score')
    ).order_by('-count')
    
    # Get AI data (cached separately)
    ai_cache_key = f'ai_data_{user.id}'
    ai_data = cache.get(ai_cache_key)
    if not ai_data:
        ai_suggestions = get_ai_suggestions(user)
        from .dashboard_ai import generate_dashboard_recommendations
        ai_recommendations = generate_dashboard_recommendations(user)
        ai_data = {'ai_suggestions': ai_suggestions, 'ai_recommendations': ai_recommendations}
        cache.set(ai_cache_key, ai_data, 1800)  # 30 minutes
    
    # Get gamification data
    from .models import UserXP, UserAchievement
    user_xp, created = UserXP.objects.get_or_create(user=user)
    recent_achievements = UserAchievement.objects.filter(user=user).order_by('-earned_at')[:3]
    leaderboard = UserXP.objects.select_related('user').order_by('-total_xp')[:10]
    
    context = {
        'quizzes_completed': quizzes_completed, 'avg_score': avg_score, 'current_streak': current_streak,
        'recent_activity': recent_activity, 'quiz_history_summary': quiz_history_summary,
        'user_xp': user_xp, 'recent_achievements': recent_achievements, 'leaderboard': leaderboard,
        **ai_data
    }
    
    cache.set(cache_key, context, 300)  # 5 minutes
    return render(request, 'userdashboard.html', context)

def calculate_streak(user):
    """Calculate the user's current quiz streak"""
    # This is a simplified implementation
    # You might want to implement a more robust streak calculation
    today = timezone.now().date()
    streak = 0
    
    # Check if user took a quiz today
    if QuizAttempt.objects.filter(user=user, attempt_date=today).exists():
        streak += 1
        # Check previous days
        for i in range(1, 7):  # Check up to 6 previous days
            previous_day = today - timedelta(days=i)
            if QuizAttempt.objects.filter(user=user, attempt_date=previous_day).exists():
                streak += 1
            else:
                break
    
    return streak

def analyze_topic_performance(user, topic, selected_difficulty):
    """Analyze user performance for specific topic and difficulty"""
    from django.db.models import Avg, Count
    
    # Get attempts for this specific topic by difficulty
    easy_attempts = QuizAttempt.objects.filter(user=user, topic=topic, difficulty='Easy')
    medium_attempts = QuizAttempt.objects.filter(user=user, topic=topic, difficulty='Medium')
    hard_attempts = QuizAttempt.objects.filter(user=user, topic=topic, difficulty='Hard')
    
    # Check if user is skipping levels without proper foundation
    if selected_difficulty == 'Medium' and easy_attempts.count() < 3:
        return {
            'type': 'suggest_downgrade',
            'current_level': 'Medium',
            'suggested_level': 'Easy',
            'topic': topic,
            'message': f'Consider starting with Easy level in {topic} first. You have only {easy_attempts.count()} Easy attempts. Build a strong foundation before advancing!',
            'attempts': easy_attempts.count(),
            'average': 0
        }
    
    if selected_difficulty == 'Hard' and (easy_attempts.count() < 3 or medium_attempts.count() < 3):
        missing_level = 'Easy' if easy_attempts.count() < 3 else 'Medium'
        return {
            'type': 'suggest_downgrade',
            'current_level': 'Hard',
            'suggested_level': missing_level,
            'topic': topic,
            'message': f'Hard level requires solid foundation. You need more practice in {missing_level} level for {topic}. Start with {missing_level} to build confidence!',
            'attempts': easy_attempts.count() + medium_attempts.count(),
            'average': 0
        }
    
    # If user selected Easy but is eligible for Medium
    if selected_difficulty == 'Easy' and easy_attempts.count() >= 5:
        easy_avg = easy_attempts.aggregate(avg=Avg('score'))['avg'] or 0
        if easy_avg >= 80:
            return {
                'type': 'suggest_upgrade',
                'current_level': 'Easy',
                'suggested_level': 'Medium',
                'topic': topic,
                'message': f'You\'ve mastered Easy level in {topic} with {easy_attempts.count()} quizzes and {easy_avg:.1f}% average. Consider trying Medium level for better growth!',
                'attempts': easy_attempts.count(),
                'average': easy_avg
            }
    
    # If user selected Medium but is eligible for Hard
    if selected_difficulty == 'Medium' and medium_attempts.count() >= 5:
        medium_avg = medium_attempts.aggregate(avg=Avg('score'))['avg'] or 0
        if medium_avg >= 75:
            return {
                'type': 'suggest_upgrade',
                'current_level': 'Medium',
                'suggested_level': 'Hard',
                'topic': topic,
                'message': f'Excellent progress in {topic} Medium level with {medium_attempts.count()} quizzes and {medium_avg:.1f}% average. Ready for Hard level challenge?',
                'attempts': medium_attempts.count(),
                'average': medium_avg
            }
    
    # If user selected Hard and has mastered it
    if selected_difficulty == 'Hard' and hard_attempts.count() >= 3:
        hard_avg = hard_attempts.aggregate(avg=Avg('score'))['avg'] or 0
        if hard_avg >= 80:
            return {
                'type': 'topic_mastered',
                'current_level': 'Hard',
                'suggested_level': 'New Topic',
                'topic': topic,
                'message': f'Outstanding! You\'ve mastered {topic} Hard level with {hard_attempts.count()} quizzes and {hard_avg:.1f}% average. Consider exploring a new topic!',
                'attempts': hard_attempts.count(),
                'average': hard_avg
            }
    
    return None

def get_level_progression_suggestion(user):
    """Check user performance and suggest next level progression for specific topics"""
    from django.db.models import Avg, Count
    
    # Get user's most active topic
    topic_stats = QuizAttempt.objects.filter(user=user).values('topic').annotate(
        count=Count('id'), avg_score=Avg('score')
    ).order_by('-count').first()
    
    if not topic_stats:
        return None
    
    main_topic = topic_stats['topic']
    
    # Get attempts for this specific topic by difficulty
    easy_attempts = QuizAttempt.objects.filter(user=user, topic=main_topic, difficulty='Easy')
    medium_attempts = QuizAttempt.objects.filter(user=user, topic=main_topic, difficulty='Medium')
    hard_attempts = QuizAttempt.objects.filter(user=user, topic=main_topic, difficulty='Hard')
    
    # Get most common subtopic for this topic
    subtopic_stats = QuizAttempt.objects.filter(user=user, topic=main_topic).values('subtopic').annotate(
        count=Count('id')
    ).order_by('-count').first()
    main_subtopic = subtopic_stats['subtopic'] if subtopic_stats else 'General'
    
    # Check Easy to Medium progression for this topic
    if easy_attempts.count() >= 5:
        easy_avg = easy_attempts.aggregate(avg=Avg('score'))['avg'] or 0
        if easy_avg >= 80:
            return {
                'type': 'level_up',
                'current_level': 'Easy',
                'next_level': 'Medium',
                'topic': main_topic,
                'subtopic': main_subtopic,
                'message': f'Great job in {main_topic}! You\'ve completed {easy_attempts.count()} Easy quizzes with {easy_avg:.1f}% average. Ready for Medium level?',
                'attempts': easy_attempts.count(),
                'average': easy_avg
            }
    
    # Check Medium to Hard progression for this topic
    if medium_attempts.count() >= 5:
        medium_avg = medium_attempts.aggregate(avg=Avg('score'))['avg'] or 0
        if medium_avg >= 75:
            return {
                'type': 'level_up',
                'current_level': 'Medium',
                'next_level': 'Hard',
                'topic': main_topic,
                'subtopic': main_subtopic,
                'message': f'Excellent progress in {main_topic}! You\'ve completed {medium_attempts.count()} Medium quizzes with {medium_avg:.1f}% average. Time for Hard level?',
                'attempts': medium_attempts.count(),
                'average': medium_avg
            }
    
    # Check Hard to Next Topic progression
    if hard_attempts.count() >= 3:
        hard_avg = hard_attempts.aggregate(avg=Avg('score'))['avg'] or 0
        if hard_avg >= 80:
            return {
                'type': 'next_topic',
                'current_level': 'Hard',
                'next_level': 'New Topic',
                'topic': main_topic,
                'subtopic': main_subtopic,
                'message': f'Outstanding! You\'ve mastered {main_topic} Hard level with {hard_attempts.count()} quizzes and {hard_avg:.1f}% average. Explore a new topic?',
                'attempts': hard_attempts.count(),
                'average': hard_avg
            }
    
    return None

# You can remove this function if you want to use user_logout for both
def userlogout(request):
    auth_logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('home')

def all_users_view(request):
    if not (request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)):
        messages.error(request, 'You need to login as admin!')
        return redirect('adminlogin')
    
    users = User.objects.all().order_by('-date_joined')
    # Add quiz count for each user
    for user in users:
        user.quiz_count = QuizAttempt.objects.filter(user=user).count()
    
    return render(request, 'all_users.html', {'users': users})

def user_management_view(request):
    if not request.session.get('admin'):
        messages.error(request, 'You need to login as admin!')
        return redirect('adminlogin')
    
    users = User.objects.all().order_by('-date_joined')
    return render(request, 'user_management.html', {'users': users})

def content_moderation_view(request):
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, 'You need to login as admin!')
        return redirect('adminlogin')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        question_ids = request.POST.getlist('question_ids')
        
        if action == 'reject' and question_ids:
            count = 0
            for qid in question_ids:
                if qid.startswith('gen_'):
                    GeneratedMCQ.objects.filter(id=qid[4:]).delete()
                    count += 1
                elif qid.startswith('pdf_'):
                    PDFUpload.objects.filter(id=qid[4:]).delete()
                    count += 1
            messages.success(request, f'Deleted {count} questions')
        
        return redirect('content_moderation')
    
    # Get all MCQs from both tables
    pdf_questions = PDFUpload.objects.all().order_by('-uploaded_at')
    generated_questions = GeneratedMCQ.objects.all().order_by('-created_at')
    
    # Combine questions with source info
    all_questions = []
    for q in pdf_questions:
        all_questions.append({
            'id': f'pdf_{q.id}',
            'source': 'PDF Upload',
            'topic': q.topic,
            'subtopic': q.subtopic,
            'difficulty': q.difficulty,
            'question': q.question,
            'created_at': q.uploaded_at,
            'approved': True
        })
    
    for q in generated_questions:
        all_questions.append({
            'id': f'gen_{q.id}',
            'source': 'AI Generated',
            'topic': q.topic,
            'subtopic': q.subtopic,
            'difficulty': q.difficulty,
            'question': q.question,
            'created_at': q.created_at,
            'approved': True
        })
    
    # Sort by creation date
    all_questions.sort(key=lambda x: x['created_at'], reverse=True)
    
    return render(request, 'content_moderation.html', {'questions': all_questions})

def analytics_view(request):
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, 'You need to login as admin!')
        return redirect('adminlogin')
    
    from datetime import datetime, timedelta
    from django.db.models import Q
    
    # User growth data - Week, Month, Year
    now = timezone.now()
    
    # Weekly data (last 7 days)
    week_data = []
    for i in range(7):
        day = now - timedelta(days=6-i)
        count = User.objects.filter(date_joined__date=day.date()).count()
        week_data.append({'label': day.strftime('%a'), 'count': count})
    
    # Monthly data (last 12 months)
    month_data = []
    for i in range(12):
        month_start = now.replace(day=1) - timedelta(days=30*i)
        month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        count = User.objects.filter(date_joined__date__range=[month_start.date(), month_end.date()]).count()
        month_data.insert(0, {'label': month_start.strftime('%b %Y'), 'count': count})
    
    # Yearly data (last 5 years)
    year_data = []
    for i in range(5):
        year = now.year - 4 + i
        count = User.objects.filter(date_joined__year=year).count()
        year_data.append({'label': str(year), 'count': count})
    
    # Real quiz performance by topic
    quiz_stats = QuizAttempt.objects.values('topic').annotate(
        avg_score=Avg('score'), count=Count('id')
    ).order_by('-count')[:8]
    
    # Real question distribution by topic
    question_stats = {}
    for item in PDFUpload.objects.values('topic').annotate(count=Count('id')):
        question_stats[item['topic']] = question_stats.get(item['topic'], 0) + item['count']
    for item in GeneratedMCQ.objects.values('topic').annotate(count=Count('id')):
        question_stats[item['topic']] = question_stats.get(item['topic'], 0) + item['count']
    
    # Real daily quiz attempts
    seven_days_ago = now - timedelta(days=7)
    daily_attempts = []
    for i in range(7):
        day = seven_days_ago + timedelta(days=i)
        count = QuizAttempt.objects.filter(attempt_date=day.date()).count()
        daily_attempts.append({'date': day.strftime('%m-%d'), 'count': count})
    
    # Real performance distribution
    performance_ranges = [
        {'range': '90-100%', 'count': QuizAttempt.objects.filter(score__gte=90).count()},
        {'range': '80-89%', 'count': QuizAttempt.objects.filter(score__gte=80, score__lt=90).count()},
        {'range': '70-79%', 'count': QuizAttempt.objects.filter(score__gte=70, score__lt=80).count()},
        {'range': '60-69%', 'count': QuizAttempt.objects.filter(score__gte=60, score__lt=70).count()},
        {'range': 'Below 60%', 'count': QuizAttempt.objects.filter(score__lt=60).count()},
    ]
    
    context = {
        'week_data': week_data, 'month_data': month_data, 'year_data': year_data,
        'quiz_stats': list(quiz_stats), 'question_stats': question_stats, 'daily_attempts': daily_attempts,
        'performance_ranges': performance_ranges, 'total_users': User.objects.count(),
        'total_quizzes': QuizAttempt.objects.count(),
        'total_questions': PDFUpload.objects.count() + GeneratedMCQ.objects.count(),
        'avg_platform_score': QuizAttempt.objects.aggregate(avg=Avg('score'))['avg'] or 0,
    }
    
    return render(request, 'analytics.html', context)

def system_settings_view(request):

    if not request.session.get('admin'):
        messages.error(request, 'You need to login as admin!')
        return redirect('adminlogin')
    
    return render(request, 'system_settings.html')

@login_required
def start_quiz_view(request):
    if request.method == 'POST':
        topic = request.POST.get('topic')
        subtopic = request.POST.get('subtopic', '').strip()
        difficulty = request.POST.get('difficulty', '').strip()
        try:
            num_questions = int(request.POST.get('num_questions', 10))
        except ValueError:
            num_questions = 10
        
        # Check if user wants to proceed after seeing analysis
        proceed = request.POST.get('proceed')
        if not proceed:
            # Analyze user performance for this topic
            analysis = analyze_topic_performance(request.user, topic, difficulty)
            if analysis:
                context = {
                    'show_analysis': True,
                    'analysis': analysis,
                    'selected_topic': topic,
                    'selected_subtopic': subtopic,
                    'selected_difficulty': difficulty,
                    'selected_questions': num_questions,
                    'topics': get_available_topics(),
                    'topic_subtopics': json.dumps(get_topic_subtopics()),
                    'subtopic_difficulties': json.dumps(get_subtopic_difficulties()),
                    'total_questions': get_total_questions_count()
                }
                return render(request, 'start_quiz.html', context)
        
        # Debug logging
        print(f"DEBUG: Quiz filters - Topic: '{topic}', Subtopic: '{subtopic}', Difficulty: '{difficulty}'")
        
        # Get questions from both PDFUpload and GeneratedMCQ tables
        pdf_questions = PDFUpload.objects.filter(topic=topic)
        generated_questions = GeneratedMCQ.objects.filter(topic=topic)
        
        print(f"DEBUG: Initial questions - PDF: {pdf_questions.count()}, Generated: {generated_questions.count()}")
        
        # Apply subtopic filter if provided (only if not empty)
        if subtopic and subtopic != "":
            pdf_questions = pdf_questions.filter(subtopic=subtopic)
            generated_questions = generated_questions.filter(subtopic=subtopic)
            print(f"DEBUG: After subtopic filter - PDF: {pdf_questions.count()}, Generated: {generated_questions.count()}")
        
        # Apply difficulty filter if provided (only if not empty)
        if difficulty and difficulty != "":
            pdf_questions = pdf_questions.filter(difficulty=difficulty)
            generated_questions = generated_questions.filter(difficulty=difficulty)
            print(f"DEBUG: After difficulty filter - PDF: {pdf_questions.count()}, Generated: {generated_questions.count()}")
        
        # Combine questions from both sources
        all_questions = []
        
        # Add PDF questions
        for q in pdf_questions:
            all_questions.append({
                'id': f'pdf_{q.id}',
                'source': 'pdf',
                'topic': q.topic,
                'subtopic': q.subtopic,
                'difficulty': q.difficulty,
                'question_no': q.question_no,
                'question_text': q.question,
                'optionA': q.option1,
                'optionB': q.option2,
                'optionC': q.option3,
                'optionD': q.option4,
                'correct_answer': q.correct_answer
            })
        
        # Add Generated questions
        for q in generated_questions:
            all_questions.append({
                'id': f'gen_{q.id}',
                'source': 'generated',
                'topic': q.topic,
                'subtopic': q.subtopic,
                'difficulty': q.difficulty,
                'question_no': q.question_no,
                'question_text': q.question,
                'optionA': q.option1,
                'optionB': q.option2,
                'optionC': q.option3,
                'optionD': q.option4,
                'correct_answer': q.correct_answer
            })
        
        print(f"DEBUG: Total combined questions: {len(all_questions)}")
        
        # Shuffle and select random questions
        if len(all_questions) > num_questions:
            questions = random.sample(all_questions, num_questions)
        else:
            questions = all_questions
            random.shuffle(questions)
        
        print(f"DEBUG: Final selected questions: {len(questions)}")
        
        if not questions:
            # Show topic request option
            context = {
                'no_questions': True,
                'missing_topic': topic,
                'missing_subtopic': subtopic,
                'missing_difficulty': difficulty,
                'topics': topics,
                'topic_subtopics': json.dumps(topic_subtopics),
                'subtopic_difficulties': json.dumps(subtopic_difficulties),
                'total_questions': total_questions
            }
            return render(request, 'start_quiz.html', context)
        
        # Questions are already prepared in the correct format
        questions_data = questions
        
        # Store questions in session for the quiz
        request.session['quiz_questions'] = questions_data
        request.session['current_question_index'] = 0
        request.session['quiz_score'] = 0
        request.session['quiz_answers'] = []
        request.session['quiz_topic'] = topic
        request.session['quiz_subtopic'] = subtopic or 'All Subtopics'
        request.session['quiz_difficulty'] = difficulty or 'All Difficulties'
        request.session['total_questions'] = len(questions_data)
        
        return redirect('quiz_question')
    
    # GET request - show the selection form
    # Get unique topics from both tables
    pdf_topics = set(PDFUpload.objects.values_list('topic', flat=True).distinct())
    gen_topics = set(GeneratedMCQ.objects.values_list('topic', flat=True).distinct())
    topics = pdf_topics.union(gen_topics)
    
    # Get subtopics grouped by topic from both tables
    topic_subtopics = {}
    subtopic_difficulties = {}
    
    for topic in topics:
        # Get subtopics from both tables
        pdf_subtopics = set(PDFUpload.objects.filter(topic=topic).values_list('subtopic', flat=True).distinct())
        gen_subtopics = set(GeneratedMCQ.objects.filter(topic=topic).values_list('subtopic', flat=True).distinct())
        all_subtopics = pdf_subtopics.union(gen_subtopics)
        topic_subtopics[topic] = list(all_subtopics)
        
        # Get difficulties for each subtopic from both tables
        for subtopic in topic_subtopics[topic]:
            pdf_difficulties = set(PDFUpload.objects.filter(
                topic=topic, subtopic=subtopic
            ).values_list('difficulty', flat=True).distinct())
            gen_difficulties = set(GeneratedMCQ.objects.filter(
                topic=topic, subtopic=subtopic
            ).values_list('difficulty', flat=True).distinct())
            all_difficulties = pdf_difficulties.union(gen_difficulties)
            subtopic_difficulties[f"{topic}_{subtopic}"] = list(all_difficulties)
    
    total_questions = PDFUpload.objects.count() + GeneratedMCQ.objects.count()
    
    # Check for level progression suggestions
    progression_suggestion = None
    if request.user.is_authenticated:
        progression_suggestion = get_level_progression_suggestion(request.user)
    
    return render(request, 'start_quiz.html', {
        'topics': topics, 
        'topic_subtopics': json.dumps(topic_subtopics),  # Pass to template as JSON
        'subtopic_difficulties': json.dumps(subtopic_difficulties),  # Pass difficulties as JSON
        'total_questions': total_questions,
        'progression_suggestion': progression_suggestion
    })
    
@login_required
def quiz_question_view(request):
    if 'quiz_questions' not in request.session:
        return redirect('start_quiz')
    
    questions = request.session['quiz_questions']
    current_index = request.session['current_question_index']
    
    # Check if quiz is completed
    if current_index >= len(questions):
        correct_answers = request.session['quiz_score']
        wrong_answers = request.session['total_questions'] - correct_answers
        score = request.session['quiz_score']
        total = request.session['total_questions']
        percentage = (score / total) * 100
        
        # Calculate total time taken in minutes and get difficulty
        total_time_seconds = sum(answer.get('time_taken', 0) for answer in request.session.get('quiz_answers', []))
        total_time_minutes = round(total_time_seconds / 60, 2)  # Convert to minutes
        quiz_difficulty = request.session.get('quiz_difficulty', 'Medium')
        
        # Save quiz attempt to database
        quiz_attempt = QuizAttempt(
            user=request.user,
            score=percentage,
            topic=request.session['quiz_topic'],
            subtopic=request.session['quiz_subtopic'] or 'All Subtopics',
            correct_answers=correct_answers,
            wrong_answers=wrong_answers,
            total_questions=total,
            time_taken=total_time_minutes,
            difficulty=quiz_difficulty,
        )
        quiz_attempt.save()
        
        # Gamification: Award XP and check achievements
        from .models import UserXP, check_achievements
        from django.core.cache import cache
        
        user_xp, created = UserXP.objects.get_or_create(user=request.user)
        user_xp.add_xp(10 + (5 if percentage >= 80 else 0))  # Bonus for high score
        user_xp.update_streak()
        
        new_achievements = check_achievements(request.user)
        
        # Clear user cache after quiz completion
        cache.delete(f'dashboard_data_{request.user.id}')
        cache.delete(f'progress_data_{request.user.id}')
        
        # Get detailed quiz results with wrong answers
        quiz_answers = request.session.get('quiz_answers', [])
        wrong_answers_details = []
        for answer in quiz_answers:
            if not answer['is_correct']:
                # Find the question details
                question_id = answer['question_id']
                if question_id.startswith('pdf_'):
                    try:
                        q = PDFUpload.objects.get(id=question_id[4:])
                        wrong_answers_details.append({
                            'question': q.question,
                            'user_answer': answer['user_answer'],
                            'correct_answer': q.correct_answer,
                            'options': {'A': q.option1, 'B': q.option2, 'C': q.option3, 'D': q.option4}
                        })
                    except PDFUpload.DoesNotExist:
                        pass
                elif question_id.startswith('gen_'):
                    try:
                        q = GeneratedMCQ.objects.get(id=question_id[4:])
                        wrong_answers_details.append({
                            'question': q.question,
                            'user_answer': answer['user_answer'],
                            'correct_answer': q.correct_answer,
                            'options': {'A': q.option1, 'B': q.option2, 'C': q.option3, 'D': q.option4}
                        })
                    except GeneratedMCQ.DoesNotExist:
                        pass
        
        # Prepare context for results page
        context = {
            'quiz_complete': True,
            'score': score,
            'total': total,
            'percentage': percentage,
            'topic': request.session['quiz_topic'],
            'subtopic': request.session['quiz_subtopic'] or 'All Subtopics',
            'wrong_answers': wrong_answers_details,
            'new_achievements': new_achievements if new_achievements else None
        }
        
        # Clear session data
        for key in ['quiz_questions', 'current_question_index', 'quiz_score', 
                   'quiz_topic', 'quiz_subtopic', 'quiz_difficulty', 'quiz_answers', 'total_questions']:
            request.session.pop(key, None)
        
        return render(request, 'quiz_question.html', context)
    
    # Show current question
    question = questions[current_index]
    return render(request, 'quiz_question.html', {
        'question': question,
        'question_number': current_index + 1,
        'total_questions': len(questions),
        'quiz_complete': False
    })

@login_required
def process_answer_view(request):
    if request.method == 'POST' and 'quiz_questions' in request.session:
        user_answer = request.POST.get('answer')
        confidence = request.POST.get('confidence', 3)
        time_taken = request.POST.get('time_taken', 0)
        current_index = request.session['current_question_index']
        questions = request.session['quiz_questions']
        
        if current_index < len(questions):
            current_question = questions[current_index]
            correct_answer = current_question['correct_answer']
            
            # Store answer details for analytics
            if 'quiz_answers' not in request.session:
                request.session['quiz_answers'] = []
            
            answer_data = {
                'question_id': current_question['id'],
                'user_answer': user_answer,
                'correct_answer': correct_answer,
                'is_correct': user_answer == correct_answer,
                'confidence': int(confidence) if confidence.isdigit() else 3,
                'time_taken': int(time_taken) if time_taken.isdigit() else 0,
                'difficulty': current_question['difficulty']
            }
            
            request.session['quiz_answers'].append(answer_data)
            
            if user_answer == correct_answer:
                request.session['quiz_score'] += 1
            
            # Move to next question
            request.session['current_question_index'] += 1
            request.session.modified = True
        
        return redirect('quiz_question')
    
    return redirect('start_quiz')

@login_required
def progress_view(request):
    from django.core.cache import cache
    user = request.user
    cache_key = f'progress_data_{user.id}'
    
    cached_data = cache.get(cache_key)
    if cached_data:
        return render(request, 'progress.html', cached_data)
    
    progress_data = QuizAttempt.objects.filter(user=user).values('topic').annotate(
        avg_score=Avg('score'), count=Count('id'), correct_answers=Avg('correct_answers'),
        wrong_answers=Avg('wrong_answers'), total_questions=Avg('total_questions')
    ).order_by('-avg_score')
    
    total_quizzes = QuizAttempt.objects.filter(user=user).count()
    overall_average = QuizAttempt.objects.filter(user=user).aggregate(avg=Avg('score'))['avg'] or 0
    current_streak = calculate_streak(user)
    recent_activity = QuizAttempt.objects.filter(user=user).order_by('-attempt_date')[:5]
    
    # AI insights cached separately
    ai_cache_key = f'progress_ai_{user.id}'
    ai_insights = cache.get(ai_cache_key)
    if not ai_insights:
        from .llm_client import generate_llm_insights
        ai_insights = generate_llm_insights(user)
        cache.set(ai_cache_key, ai_insights, 1800)  # 30 minutes
    
    context = {
        'progress_data': progress_data, 'total_quizzes': total_quizzes, 'overall_average': overall_average,
        'current_streak': current_streak, 'recent_activity': recent_activity, 'ai_insights': ai_insights,
        'total_time': '24h'
    }

    cache.set(cache_key, context, 600)  # 10 minutes
    return render(request, 'progress.html', context)

@login_required
def quiz_history_view(request):
    user = request.user
    # Get quiz history
    quiz_history = QuizAttempt.objects.filter(user=user)
    return render(request, 'quiz_history.html', {'quiz_history': quiz_history})

@login_required
def profile_view(request):
    return render(request, 'profile.html', {'user': request.user})

@login_required
def settings_view(request):
    if request.method == "POST":
        section = request.POST.get('section')
        
        if section == 'profile':
            # Update profile information
            user = request.user
            user.email = request.POST.get('email', user.email)
            user.first_name = request.POST.get('first_name', user.first_name)
            user.last_name = request.POST.get('last_name', user.last_name)
            user.save()
            
            # Update profile fields
            profile = user.profile
            profile.contact = request.POST.get('contact', profile.contact)
            profile.gender = request.POST.get('gender', profile.gender)
            profile.save()
            
            messages.success(request, 'Profile updated successfully!')
            
        elif section == 'password':
            # Handle password change
            current_password = request.POST.get('current_password')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            
            if not request.user.check_password(current_password):
                messages.error(request, 'Current password is incorrect.')
            elif new_password != confirm_password:
                messages.error(request, 'New passwords do not match.')
            elif len(new_password) < 8:
                messages.error(request, 'Password must be at least 8 characters long.')
            else:
                request.user.set_password(new_password)
                request.user.save()
                messages.success(request, 'Password changed successfully!')
                
        elif section in ['preferences', 'notifications']:
            # Handle preferences and notifications
            messages.success(request, f'{section.title()} updated successfully!')
            
        return redirect('settings')
    
    return render(request, 'settings.html')

def help_view(request):
    return render(request, 'help.html')

@login_required
def regenerate_insights_view(request):
    if request.method == 'POST':
        try:
            from django.core.cache import cache
            from .llm_client import generate_llm_insights
            
            # Clear cache and regenerate
            cache.delete(f'progress_ai_{request.user.id}')
            cache.delete(f'ai_data_{request.user.id}')
            
            ai_insights = generate_llm_insights(request.user)
            cache.set(f'progress_ai_{request.user.id}', ai_insights, 1800)
            
            return JsonResponse({'success': True, 'insights': ai_insights})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid method'})

@login_required
def explain_insight_view(request):
    if request.method == 'POST':
        try:
            import json
            import google.generativeai as genai
            
            data = json.loads(request.body)
            insight = data.get('insight', '')
            
            if not insight:
                return JsonResponse({'success': False, 'error': 'No insight provided'})
            
            genai.configure(api_key="AIzaSyAr4zAzbPoB7UCzA9N8BwJCq5CQYMZQPFk")
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            prompt = f"""You are a study coach explaining your recommendations. Explain why this study advice was given in 1-2 sentences:
            
            Advice: "{insight}"
            
            Provide a brief, clear explanation of the reasoning behind this recommendation."""
            
            response = model.generate_content(prompt)
            explanation = response.text.strip()
            return JsonResponse({'success': True, 'explanation': explanation})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'API Error: {str(e)}'})
    return JsonResponse({'success': False, 'error': 'Invalid method'})

@login_required
def rate_insight_view(request):
    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)
            insight = data.get('insight', '')
            rating = data.get('rating', '')
            
            # Store feedback (you can save to database for analytics)
            return JsonResponse({'success': True, 'message': 'Feedback recorded'})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid method'})

@login_required
def chatbot_view(request):
    return render(request, 'chatbot.html')

@login_required
def chatbot_explain(request):
    if request.method == 'POST':
        try:
            import json
            import google.generativeai as genai
            
            data = json.loads(request.body)
            topic = data.get('topic', '').strip()
            
            if not topic:
                return JsonResponse({'success': False, 'error': 'Please enter a topic'})
            
            genai.configure(api_key="AIzaSyAr4zAzbPoB7UCzA9N8BwJCq5CQYMZQPFk")
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            prompt = f"""Explain "{topic}" in simple, easy-to-understand terms. Use:
            - Simple language (avoid jargon)
            - Real-world examples
            - Step-by-step breakdown if needed
            - Analogies when helpful
            - Keep it concise but comprehensive
            
            Make it suitable for someone learning this topic for the first time."""
            
            response = model.generate_content(prompt)
            explanation = response.text.strip()
            
            return JsonResponse({
                'success': True, 
                'explanation': explanation,
                'topic': topic
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Error: {str(e)}'})
    
    return JsonResponse({'success': False, 'error': 'Invalid method'})

@login_required
def browse_topics_view(request):
    from django.db.models import Count, Avg, Q
    from .adaptive_quiz import get_adaptive_difficulty
    
    # Define base topics with categories
    base_topics = {
        'Programming': [
            {'name': 'Python', 'subtopics': ['Basics', 'OOP', 'Data Structures', 'Web Development']},
            {'name': 'Java', 'subtopics': ['Fundamentals', 'OOP', 'Collections', 'Spring Framework']},
            {'name': 'JavaScript', 'subtopics': ['ES6+', 'DOM', 'React', 'Node.js']},
            {'name': 'C++', 'subtopics': ['Basics', 'STL', 'Memory Management', 'Advanced']}
        ],
        'Data Science': [
            {'name': 'Machine Learning', 'subtopics': ['Supervised', 'Unsupervised', 'Deep Learning', 'NLP']},
            {'name': 'Statistics', 'subtopics': ['Descriptive', 'Inferential', 'Probability', 'Hypothesis Testing']},
            {'name': 'Data Analysis', 'subtopics': ['Pandas', 'NumPy', 'Visualization', 'SQL']}
        ],
        'Web Development': [
            {'name': 'Frontend', 'subtopics': ['HTML/CSS', 'JavaScript', 'React', 'Vue.js']},
            {'name': 'Backend', 'subtopics': ['APIs', 'Databases', 'Authentication', 'Deployment']}
        ],
        'Computer Science': [
            {'name': 'Algorithms', 'subtopics': ['Sorting', 'Searching', 'Graph', 'Dynamic Programming']},
            {'name': 'Data Structures', 'subtopics': ['Arrays', 'Trees', 'Graphs', 'Hash Tables']},
            {'name': 'System Design', 'subtopics': ['Scalability', 'Databases', 'Caching', 'Microservices']}
        ]
    }
    
    # Get user's quiz attempts for progress tracking
    user_attempts = QuizAttempt.objects.filter(user=request.user)
    
    # Enrich topics with progress data
    topic_categories = {}
    for category, topics in base_topics.items():
        enriched_topics = []
        for topic in topics:
            topic_name = topic['name']
            attempts = user_attempts.filter(topic=topic_name)
            
            if attempts.exists():
                avg_score = attempts.aggregate(avg=Avg('score'))['avg']
                total_attempts = attempts.count()
                
                # Determine mastery level
                if avg_score >= 85 and total_attempts >= 3:
                    status = 'mastered'
                elif avg_score >= 60 or total_attempts >= 1:
                    status = 'in_progress'
                else:
                    status = 'not_started'
            else:
                avg_score = 0
                total_attempts = 0
                status = 'not_started'
            
            enriched_topic = {
                'name': topic_name,
                'subtopics': topic['subtopics'],
                'avg_score': avg_score or 0,
                'total_attempts': total_attempts,
                'status': status,
                'difficulty': get_adaptive_difficulty(request.user, topic_name)
            }
            enriched_topics.append(enriched_topic)
        
        topic_categories[category] = enriched_topics
    
    # Get learning paths
    learning_paths = [
        {
            'name': 'Python Mastery Path',
            'topics': ['Python', 'Data Structures', 'Algorithms'],
            'description': 'Complete Python programming journey',
            'duration': '4-6 weeks',
            'level': 'Beginner to Advanced'
        },
        {
            'name': 'Data Science Path',
            'topics': ['Statistics', 'Machine Learning', 'Data Analysis'],
            'description': 'Become a data science expert',
            'duration': '6-8 weeks',
            'level': 'Intermediate'
        },
        {
            'name': 'Full Stack Developer Path',
            'topics': ['Frontend', 'Backend', 'JavaScript'],
            'description': 'End-to-end web development skills',
            'duration': '8-10 weeks',
            'level': 'Beginner to Advanced'
        }
    ]
    
    context = {
        'topic_categories': topic_categories,
        'learning_paths': learning_paths
    }
    
    return render(request, 'browse_topics.html', context)
    


@login_required
def learning_path_detail_view(request, path_name):
    # Define detailed learning paths
    path_details = {
        'Python Mastery Path': {
            'name': 'Python Mastery Path',
            'description': 'Complete Python programming journey from basics to advanced concepts',
            'duration': '4-6 weeks',
            'level': 'Beginner to Advanced',
            'modules': [
                {'name': 'Python Basics', 'duration': '1 week', 'topics': ['Variables', 'Data Types', 'Control Flow'], 'quizzes': 5},
                {'name': 'Object-Oriented Programming', 'duration': '1 week', 'topics': ['Classes', 'Inheritance', 'Polymorphism'], 'quizzes': 4},
                {'name': 'Data Structures', 'duration': '1-2 weeks', 'topics': ['Lists', 'Dictionaries', 'Sets', 'Tuples'], 'quizzes': 6},
                {'name': 'Advanced Python', 'duration': '1-2 weeks', 'topics': ['Decorators', 'Generators', 'Context Managers'], 'quizzes': 4}
            ],
            'features': ['Interactive Quizzes', 'AI-Powered Feedback', 'Progress Tracking', 'Certificate of Completion'],
            'prerequisites': 'Basic computer knowledge',
            'outcomes': ['Build Python applications', 'Understand OOP concepts', 'Master data structures']
        },
        'Data Science Path': {
            'name': 'Data Science Path',
            'description': 'Become a data science expert with statistics, ML, and analysis skills',
            'duration': '6-8 weeks',
            'level': 'Intermediate',
            'modules': [
                {'name': 'Statistics Fundamentals', 'duration': '2 weeks', 'topics': ['Descriptive Stats', 'Probability', 'Distributions'], 'quizzes': 6},
                {'name': 'Machine Learning', 'duration': '3 weeks', 'topics': ['Supervised Learning', 'Unsupervised Learning', 'Deep Learning'], 'quizzes': 8},
                {'name': 'Data Analysis', 'duration': '2-3 weeks', 'topics': ['Pandas', 'NumPy', 'Visualization'], 'quizzes': 7}
            ],
            'features': ['Real Dataset Practice', 'ML Model Building', 'Data Visualization', 'Industry Projects'],
            'prerequisites': 'Basic Python knowledge, High school math',
            'outcomes': ['Build ML models', 'Analyze complex datasets', 'Create data visualizations']
        },
        'Full Stack Developer Path': {
            'name': 'Full Stack Developer Path',
            'description': 'End-to-end web development skills from frontend to backend',
            'duration': '8-10 weeks',
            'level': 'Beginner to Advanced',
            'modules': [
                {'name': 'Frontend Development', 'duration': '3 weeks', 'topics': ['HTML/CSS', 'JavaScript', 'React'], 'quizzes': 9},
                {'name': 'Backend Development', 'duration': '3 weeks', 'topics': ['APIs', 'Databases', 'Authentication'], 'quizzes': 8},
                {'name': 'Full Stack Integration', 'duration': '2-4 weeks', 'topics': ['Deployment', 'Testing', 'DevOps'], 'quizzes': 6}
            ],
            'features': ['Live Project Building', 'Portfolio Development', 'Industry Best Practices', 'Deployment Skills'],
            'prerequisites': 'Basic programming knowledge',
            'outcomes': ['Build full-stack applications', 'Deploy web applications', 'Master modern frameworks']
        }
    }
    
    path_detail = path_details.get(path_name)
    if not path_detail:
        messages.error(request, 'Learning path not found')
        return redirect('browse_topics')
    
    # Calculate user progress for this path
    user_attempts = QuizAttempt.objects.filter(user=request.user)
    total_quizzes = sum(module['quizzes'] for module in path_detail['modules'])
    completed_quizzes = 0
    
    for module in path_detail['modules']:
        for topic in module['topics']:
            completed_quizzes += user_attempts.filter(topic__icontains=topic).count()
    
    progress_percentage = min((completed_quizzes / total_quizzes) * 100, 100) if total_quizzes > 0 else 0
    
    context = {
        'path': path_detail,
        'progress_percentage': progress_percentage,
        'completed_quizzes': completed_quizzes,
        'total_quizzes': total_quizzes
    }
    
    return render(request, 'learning_path_detail.html', context)

@login_required
def request_topic_view(request):
    if request.method == 'POST':
        from .models import TopicRequest
        topic = request.POST.get('topic')
        subtopic = request.POST.get('subtopic', '')
        difficulty = request.POST.get('difficulty')
        description = request.POST.get('description')
        
        TopicRequest.objects.create(
            user=request.user,
            topic=topic,
            subtopic=subtopic,
            difficulty=difficulty,
            description=description
        )
        
        messages.success(request, 'Topic request submitted successfully! Admin will review it soon.')
        return redirect('start_quiz')
    
    return render(request, 'request_topic.html')

@login_required
def start_learning_path_view(request, path_name):
    from .models import LearningPathProgress, PDFUpload, GeneratedMCQ
    
    # Get or create learning path progress
    progress, created = LearningPathProgress.objects.get_or_create(
        user=request.user,
        path_name=path_name,
        defaults={'current_topic': 'Python'}
    )
    
    # Define path modules
    path_modules = {
        'Python Mastery Path': [
            {'name': 'Python', 'topics': ['Variables', 'Data Types', 'Control Flow']},
            {'name': 'Python', 'topics': ['Classes', 'Inheritance', 'Polymorphism']},
            {'name': 'Data Structures', 'topics': ['Lists', 'Dictionaries', 'Sets']},
            {'name': 'Python', 'topics': ['Decorators', 'Generators', 'Context Managers']}
        ],
        'Data Science Path': [
            {'name': 'Statistics', 'topics': ['Descriptive Stats', 'Probability']},
            {'name': 'Machine Learning', 'topics': ['Supervised', 'Unsupervised']},
            {'name': 'Data Analysis', 'topics': ['Pandas', 'NumPy', 'Visualization']}
        ],
        'Full Stack Developer Path': [
            {'name': 'Frontend', 'topics': ['HTML/CSS', 'JavaScript', 'React']},
            {'name': 'Backend', 'topics': ['APIs', 'Databases', 'Authentication']},
            {'name': 'JavaScript', 'topics': ['Deployment', 'Testing', 'DevOps']}
        ]
    }
    
    modules = path_modules.get(path_name, [])
    if not modules or progress.current_module >= len(modules):
        messages.error(request, 'Learning path not found or completed')
        return redirect('browse_topics')
    
    current_module = modules[progress.current_module]
    current_topic = current_module['name']
    
    # Check if topic exists in database
    pdf_questions = PDFUpload.objects.filter(topic=current_topic)
    generated_questions = GeneratedMCQ.objects.filter(topic=current_topic)
    
    if not pdf_questions.exists() and not generated_questions.exists():
        # Topic not available, show request form
        context = {
            'path_name': path_name,
            'current_module': current_module,
            'missing_topic': current_topic,
            'module_number': progress.current_module + 1,
            'total_modules': len(modules)
        }
        return render(request, 'missing_topic.html', context)
    
    # Topic exists, start quiz automatically with path settings
    # Store path info in session
    request.session['learning_path'] = path_name
    request.session['path_module'] = progress.current_module
    
    # Auto-select topic, subtopic, and difficulty for learning path
    request.session['quiz_questions'] = []
    request.session['current_question_index'] = 0
    request.session['quiz_score'] = 0
    request.session['quiz_answers'] = []
    request.session['quiz_topic'] = current_topic
    request.session['quiz_subtopic'] = 'All Subtopics'
    request.session['quiz_difficulty'] = 'Easy'  # Start with Easy for learning paths
    
    # Get questions for the current topic
    all_questions = []
    
    # Add PDF questions
    for q in pdf_questions[:10]:  # Limit to 10 questions
        all_questions.append({
            'id': f'pdf_{q.id}',
            'source': 'pdf',
            'topic': q.topic,
            'subtopic': q.subtopic,
            'difficulty': q.difficulty,
            'question_no': q.question_no,
            'question_text': q.question,
            'optionA': q.option1,
            'optionB': q.option2,
            'optionC': q.option3,
            'optionD': q.option4,
            'correct_answer': q.correct_answer
        })
    
    # Add Generated questions if needed
    if len(all_questions) < 10:
        for q in generated_questions[:10-len(all_questions)]:
            all_questions.append({
                'id': f'gen_{q.id}',
                'source': 'generated',
                'topic': q.topic,
                'subtopic': q.subtopic,
                'difficulty': q.difficulty,
                'question_no': q.question_no,
                'question_text': q.question,
                'optionA': q.option1,
                'optionB': q.option2,
                'optionC': q.option3,
                'optionD': q.option4,
                'correct_answer': q.correct_answer
            })
    
    if all_questions:
        random.shuffle(all_questions)
        request.session['quiz_questions'] = all_questions
        request.session['total_questions'] = len(all_questions)
        return redirect('quiz_question')
    else:
        messages.error(request, f'No questions available for {current_topic}')
        return redirect('browse_topics')

@login_required
def reports_view(request):
    if not request.user.is_staff:
        messages.error(request, 'Access denied')
        return redirect('userdashboard')
    
    from datetime import timedelta
    today = timezone.now().date()
    thirty_days_ago = today - timedelta(days=30)
    
    # Calculate stats
    total_users = User.objects.count()
    new_users_month = User.objects.filter(date_joined__date__gte=thirty_days_ago).count()
    active_users = User.objects.filter(is_active=True).count()
    total_questions = PDFUpload.objects.count() + GeneratedMCQ.objects.count()
    
    # Today's activity
    new_users_today = User.objects.filter(date_joined__date=today).count()
    quizzes_today = QuizAttempt.objects.filter(attempt_date=today).count()
    
    # Recent users with quiz count
    recent_users = User.objects.all().order_by('-date_joined')[:10]
    for user in recent_users:
        user.quiz_count = QuizAttempt.objects.filter(user=user).count()
    
    # Pending topic requests
    from .models import TopicRequest
    pending_requests = TopicRequest.objects.filter(status='pending').count()
    
    context = {
        'total_users': total_users,
        'new_users_month': new_users_month,
        'active_users': active_users,
        'total_questions': total_questions,
        'new_users_today': new_users_today,
        'quizzes_today': quizzes_today,
        'recent_users': recent_users,
        'pending_requests': pending_requests,
    }
    
    return render(request, 'reports.html', context)

@login_required
def real_time_analytics_api(request):
    """API endpoint for real-time analytics data"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    from datetime import timedelta
    now = timezone.now()
    today = now.date()
    
    # Real-time user growth data
    week_data = []
    for i in range(7):
        day = now - timedelta(days=6-i)
        count = User.objects.filter(date_joined__date=day.date()).count()
        week_data.append({
            'date': day.strftime('%Y-%m-%d'),
            'label': day.strftime('%a'),
            'count': count
        })
    
    # Monthly data for last 12 months
    month_data = []
    for i in range(12):
        month_start = now.replace(day=1) - timedelta(days=30*i)
        month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        count = User.objects.filter(date_joined__date__range=[month_start.date(), month_end.date()]).count()
        month_data.insert(0, {
            'date': month_start.strftime('%Y-%m'),
            'label': month_start.strftime('%b %Y'),
            'count': count
        })
    
    # Current stats
    current_stats = {
        'total_users': User.objects.count(),
        'active_users': User.objects.filter(is_active=True).count(),
        'new_today': User.objects.filter(date_joined__date=today).count(),
        'quizzes_today': QuizAttempt.objects.filter(attempt_date=today).count(),
        'avg_score': QuizAttempt.objects.aggregate(avg=Avg('score'))['avg'] or 0
    }
    
    return JsonResponse({
        'week_data': week_data,
        'month_data': month_data,
        'current_stats': current_stats,
        'timestamp': now.isoformat()
    })

@login_required
def user_performance_api(request):
    """API endpoint for individual user performance data with period filtering"""
    user = request.user
    period = request.GET.get('period', 'week')
    
    from datetime import timedelta
    now = timezone.now()
    
    # Performance data based on period
    performance_data = []
    
    if period == 'week':
        # Last 7 days
        for i in range(7):
            day = now - timedelta(days=6-i)
            attempts = QuizAttempt.objects.filter(user=user, attempt_date=day.date())
            avg_score = attempts.aggregate(avg=Avg('score'))['avg'] if attempts.exists() else 0
            quiz_count = attempts.count()
            
            performance_data.append({
                'label': day.strftime('%a'),
                'avg_score': avg_score or 0,
                'quiz_count': quiz_count,
                'date': day.strftime('%Y-%m-%d')
            })
    
    elif period == 'month':
        # Last 4 weeks
        for i in range(4):
            week_start = now - timedelta(weeks=3-i)
            week_end = week_start + timedelta(days=6)
            attempts = QuizAttempt.objects.filter(
                user=user, 
                attempt_date__range=[week_start.date(), week_end.date()]
            )
            avg_score = attempts.aggregate(avg=Avg('score'))['avg'] if attempts.exists() else 0
            quiz_count = attempts.count()
            
            performance_data.append({
                'label': f'Week {i+1}',
                'avg_score': avg_score or 0,
                'quiz_count': quiz_count,
                'date': week_start.strftime('%Y-%m-%d')
            })
    
    else:  # all time - last 12 months
        for i in range(12):
            month_start = now.replace(day=1) - timedelta(days=30*i)
            month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            attempts = QuizAttempt.objects.filter(
                user=user,
                attempt_date__range=[month_start.date(), month_end.date()]
            )
            avg_score = attempts.aggregate(avg=Avg('score'))['avg'] if attempts.exists() else 0
            quiz_count = attempts.count()
            
            performance_data.insert(0, {
                'label': month_start.strftime('%b %Y'),
                'avg_score': avg_score or 0,
                'quiz_count': quiz_count,
                'date': month_start.strftime('%Y-%m')
            })
    
    # Topic performance
    topic_performance = QuizAttempt.objects.filter(user=user).values('topic').annotate(
        avg_score=Avg('score'),
        count=Count('id')
    ).order_by('-avg_score')[:8]
    
    # Current user stats
    user_stats = {
        'total_quizzes': QuizAttempt.objects.filter(user=user).count(),
        'avg_score': QuizAttempt.objects.filter(user=user).aggregate(avg=Avg('score'))['avg'] or 0,
        'best_score': QuizAttempt.objects.filter(user=user).aggregate(max=Max('score'))['max'] or 0,
        'current_streak': calculate_streak(user)
    }
    
    return JsonResponse({
        'performance_data': performance_data,
        'topic_performance': list(topic_performance),
        'user_stats': user_stats,
        'period': period,
        'timestamp': now.isoformat()
    })

@login_required
def get_user_growth_data_api(request):
    """API for user growth data used in all users page"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    from datetime import timedelta
    now = timezone.now()
    
    # Get period from request (default to week)
    period = request.GET.get('period', 'week')
    
    if period == 'week':
        data = []
        for i in range(7):
            day = now - timedelta(days=6-i)
            count = User.objects.filter(date_joined__date=day.date()).count()
            data.append({
                'label': day.strftime('%a'),
                'count': count,
                'date': day.strftime('%Y-%m-%d')
            })
    elif period == 'month':
        data = []
        for i in range(12):
            month_start = now.replace(day=1) - timedelta(days=30*i)
            month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            count = User.objects.filter(date_joined__date__range=[month_start.date(), month_end.date()]).count()
            data.insert(0, {
                'label': month_start.strftime('%b %Y'),
                'count': count,
                'date': month_start.strftime('%Y-%m')
            })
    else:  # year
        data = []
        for i in range(5):
            year = now.year - 4 + i
            count = User.objects.filter(date_joined__year=year).count()
            data.append({
                'label': str(year),
                'count': count,
                'date': str(year)
            })
    
    return JsonResponse({
        'data': data,
        'period': period,
        'timestamp': now.isoformat()
    })

def topic_requests_admin_view(request):
    if not request.user.is_staff:
        messages.error(request, 'Access denied')
        return redirect('userdashboard')
    
    from .models import TopicRequest
    
    if request.method == 'POST':
        request_id = request.POST.get('request_id')
        action = request.POST.get('action')
        admin_notes = request.POST.get('admin_notes', '')
        
        topic_request = TopicRequest.objects.get(id=request_id)
        
        if action == 'approve':
            topic_request.status = 'approved'
        elif action == 'reject':
            topic_request.status = 'rejected'
        elif action == 'complete':
            topic_request.status = 'completed'
        elif action == 'generate_ai':
            # Auto-generate 50 questions using AI Quiz Generator
            try:
                generator = AIQuizGenerator()
                questions = generator.generate_quiz_content(
                    topic_request.topic, 
                    topic_request.subtopic or 'General', 
                    topic_request.difficulty, 
                    50
                )
                
                if questions:
                    # Create PDF
                    import os
                    from django.conf import settings
                    
                    filename = f"{topic_request.topic}_{topic_request.subtopic or 'General'}_{topic_request.difficulty}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    pdf_path = os.path.join(settings.MEDIA_ROOT, 'ai_generated_pdfs', filename)
                    
                    # Ensure directory exists
                    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
                    
                    generator.create_pdf(questions, topic_request.topic, topic_request.subtopic or 'General', topic_request.difficulty, pdf_path)
                    
                    # Save to AIGeneratedPDF database
                    AIGeneratedPDF.objects.create(
                        topic=topic_request.topic,
                        subtopic=topic_request.subtopic or 'General',
                        difficulty=topic_request.difficulty,
                        num_questions=len(questions),
                        pdf_file=f'ai_generated_pdfs/{filename}',
                        created_by=request.user
                    )
                    
                    # Save questions to GeneratedMCQ
                    for idx, q in enumerate(questions, 1):
                        GeneratedMCQ.objects.create(
                            topic=topic_request.topic,
                            subtopic=topic_request.subtopic or 'General',
                            difficulty=topic_request.difficulty,
                            question_no=idx,
                            question=q['question'],
                            option1=q['options'][0][3:] if len(q['options'][0]) > 3 else q['options'][0],
                            option2=q['options'][1][3:] if len(q['options'][1]) > 3 else q['options'][1],
                            option3=q['options'][2][3:] if len(q['options'][2]) > 3 else q['options'][2],
                            option4=q['options'][3][3:] if len(q['options'][3]) > 3 else q['options'][3],
                            correct_answer=q['correct_answer'],
                            created_by=request.user
                        )
                    
                    topic_request.status = 'completed'
                    topic_request.admin_notes = f'Auto-generated {len(questions)} questions using AI'
                    messages.success(request, f'Generated {len(questions)} questions and PDF for {topic_request.topic}')
                else:
                    messages.error(request, 'Failed to generate questions')
            except Exception as e:
                messages.error(request, f'Error generating questions: {str(e)}')
        
        topic_request.admin_notes = admin_notes
        topic_request.save()
        
        if action != 'generate_ai':
            messages.success(request, f'Topic request {action}d successfully')
        return redirect('topic_requests_admin')
    
    requests = TopicRequest.objects.all().order_by('-created_at')
    return render(request, 'topic_requests_admin.html', {'requests': requests})

@login_required
def edit_user_view(request):
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Access denied'})
    
    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)
            user_id = data.get('user_id')
            
            user = User.objects.get(id=user_id)
            user.username = data.get('username', user.username)
            user.email = data.get('email', user.email)
            user.first_name = data.get('first_name', user.first_name)
            user.last_name = data.get('last_name', user.last_name)
            user.save()
            
            return JsonResponse({'success': True, 'message': 'User updated successfully'})
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid method'})

@login_required
def block_user_view(request):
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Access denied'})
    
    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)
            user_id = data.get('user_id')
            action = data.get('action')
            
            user = User.objects.get(id=user_id)
            
            if action == 'block':
                user.is_active = False
                message = f'User {user.username} has been blocked'
            elif action == 'unblock':
                user.is_active = True
                message = f'User {user.username} has been unblocked'
            else:
                return JsonResponse({'success': False, 'error': 'Invalid action'})
            
            user.save()
            return JsonResponse({'success': True, 'message': message})
            
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid method'})

def get_available_topics():
    """Get all available topics from both tables"""
    pdf_topics = set(PDFUpload.objects.values_list('topic', flat=True).distinct())
    gen_topics = set(GeneratedMCQ.objects.values_list('topic', flat=True).distinct())
    return pdf_topics.union(gen_topics)

def get_topic_subtopics():
    """Get subtopics grouped by topic"""
    topics = get_available_topics()
    topic_subtopics = {}
    for topic in topics:
        pdf_subtopics = set(PDFUpload.objects.filter(topic=topic).values_list('subtopic', flat=True).distinct())
        gen_subtopics = set(GeneratedMCQ.objects.filter(topic=topic).values_list('subtopic', flat=True).distinct())
        topic_subtopics[topic] = list(pdf_subtopics.union(gen_subtopics))
    return topic_subtopics

def get_subtopic_difficulties():
    """Get difficulties for each topic-subtopic combination"""
    topics = get_available_topics()
    subtopic_difficulties = {}
    for topic in topics:
        topic_subtopics = get_topic_subtopics().get(topic, [])
        for subtopic in topic_subtopics:
            pdf_difficulties = set(PDFUpload.objects.filter(topic=topic, subtopic=subtopic).values_list('difficulty', flat=True).distinct())
            gen_difficulties = set(GeneratedMCQ.objects.filter(topic=topic, subtopic=subtopic).values_list('difficulty', flat=True).distinct())
            subtopic_difficulties[f"{topic}_{subtopic}"] = list(pdf_difficulties.union(gen_difficulties))
    return subtopic_difficulties

def get_total_questions_count():
    """Get total count of questions from both tables"""
    return PDFUpload.objects.count() + GeneratedMCQ.objects.count()