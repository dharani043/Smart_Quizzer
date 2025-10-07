import google.generativeai as genai
from .models import QuizAttempt, PDFUpload, GeneratedMCQ
from django.db.models import Avg

genai.configure(api_key="AIzaSyAr4zAzbPoB7UCzA9N8BwJCq5CQYMZQPFk")
model = genai.GenerativeModel('gemini-2.5-pro')

def get_adaptive_difficulty(user, topic):
    """Determine appropriate difficulty based on user performance"""
    recent_attempts = QuizAttempt.objects.filter(
        user=user, topic=topic
    ).order_by('-attempt_date')[:3]
    
    if not recent_attempts:
        return 'Easy'
    
    avg_score = sum(attempt.score for attempt in recent_attempts) / len(recent_attempts)
    
    if avg_score >= 85:
        return 'Hard'
    elif avg_score >= 70:
        return 'Medium'
    else:
        return 'Easy'

def generate_custom_quiz(topic, focus_area, num_questions=10):
    """Generate custom quiz using AI"""
    try:
        prompt = f"""Generate {num_questions} multiple choice questions about {topic} focusing on {focus_area}.

Format each question as:
Q: [question]
A) [option]
B) [option] 
C) [option]
D) [option]
Answer: [A/B/C/D]

Make questions practical and test real understanding."""

        response = model.generate_content(prompt)
        
        # Parse response into MCQ format
        questions = []
        lines = response.text.strip().split('\n')
        current_q = {}
        
        for line in lines:
            line = line.strip()
            if line.startswith('Q:'):
                if current_q:
                    questions.append(current_q)
                current_q = {'question': line[2:].strip(), 'options': []}
            elif line.startswith(('A)', 'B)', 'C)', 'D)')):
                current_q['options'].append(line[2:].strip())
            elif line.startswith('Answer:'):
                current_q['correct'] = line[7:].strip()
        
        if current_q:
            questions.append(current_q)
        
        return questions[:num_questions]
        
    except Exception as e:
        return []

def get_personalized_recommendations(user):
    """Get personalized quiz recommendations"""
    from .models import UserXP
    
    user_xp, _ = UserXP.objects.get_or_create(user=user)
    
    # Get user's performance by topic
    topic_performance = QuizAttempt.objects.filter(user=user).values('topic').annotate(
        avg_score=Avg('score')
    ).order_by('avg_score')
    
    recommendations = []
    
    # Recommend improvement for weakest topic
    if topic_performance:
        weakest = topic_performance.first()
        if weakest['avg_score'] < 70:
            recommendations.append({
                'type': 'improvement',
                'topic': weakest['topic'],
                'message': f"Focus on {weakest['topic']} - practice more to improve from {weakest['avg_score']:.1f}%",
                'difficulty': 'Easy',
                'priority': 'high'
            })
    
    # Daily streak reminder
    if user_xp.current_streak > 0:
        recommendations.append({
            'type': 'streak',
            'topic': 'Any',
            'message': f"Keep your {user_xp.current_streak}-day streak alive! Take a quick quiz today.",
            'difficulty': 'Medium',
            'priority': 'medium'
        })
    
    # Level up suggestion
    xp_to_next_level = (user_xp.level * 100) - user_xp.total_xp
    if xp_to_next_level <= 20:
        recommendations.append({
            'type': 'level_up',
            'topic': 'Any',
            'message': f"Only {xp_to_next_level} XP to level {user_xp.level + 1}! Take a quiz now.",
            'difficulty': 'Medium',
            'priority': 'high'
        })
    
    return recommendations