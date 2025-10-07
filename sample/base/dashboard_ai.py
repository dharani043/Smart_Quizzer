import google.generativeai as genai
from django.db.models import Avg, Count
from .models import QuizAttempt

# Configure Google Generative AI
genai.configure(api_key="AIzaSyAr4zAzbPoB7UCzA9N8BwJCq5CQYMZQPFk")
model = genai.GenerativeModel('gemini-2.5-pro')

def generate_dashboard_recommendations(user):
    """Generate detailed AI recommendations for user dashboard"""
    try:
        # Get comprehensive user data
        quiz_data = QuizAttempt.objects.filter(user=user).values('topic').annotate(
            avg_score=Avg('score'),
            quiz_count=Count('id'),
            total_correct=Avg('correct_answers'),
            total_wrong=Avg('wrong_answers')
        ).order_by('-avg_score')
        
        if not quiz_data:
            return "📚 Start taking quizzes to get personalized AI recommendations!"
        
        # Build detailed performance summary
        performance_summary = []
        for item in quiz_data:
            performance_summary.append(
                f"{item['topic']}: {item['avg_score']:.1f}% avg, {item['quiz_count']} quizzes, "
                f"{item['total_correct']:.1f} correct, {item['total_wrong']:.1f} wrong"
            )
        
        prompt = f"""You are an expert programming mentor. Analyze this student's quiz performance and provide detailed learning recommendations:

PERFORMANCE DATA:
{chr(10).join(performance_summary)}

Provide a comprehensive analysis covering:
1. STRENGTHS: What they excel at
2. WEAKNESSES: Areas needing improvement with specific focus points
3. NEXT STEPS: Detailed roadmap of what to learn next
4. STUDY STRATEGY: How to improve weak areas

Write 3-4 paragraphs with actionable advice. Be specific about technologies, concepts, and learning approaches."""

        response = model.generate_content(prompt)
        return response.text.strip()
        
    except Exception as e:
        return generate_fallback_dashboard_recommendations(quiz_data if 'quiz_data' in locals() else [])

def generate_fallback_dashboard_recommendations(quiz_data):
    """Fallback recommendations if AI fails"""
    if not quiz_data:
        return "📚 Complete more quizzes to unlock detailed AI recommendations!"
    
    best_topic = max(quiz_data, key=lambda x: x['avg_score'])
    worst_topic = min(quiz_data, key=lambda x: x['avg_score'])
    
    recommendations = f"""
    🎯 **Your Learning Analysis:**
    
    **Strengths:** You're performing excellently in {best_topic['topic']} with {best_topic['avg_score']:.1f}% average. This shows strong understanding of core concepts.
    
    **Areas for Improvement:** {worst_topic['topic']} needs attention with {worst_topic['avg_score']:.1f}% average. Focus on fundamentals and practice more problems.
    
    **Next Steps:** Since you're strong in {best_topic['topic']}, consider advanced topics like frameworks or libraries. For {worst_topic['topic']}, review basic concepts and take more practice quizzes.
    
    **Study Strategy:** Dedicate 70% time to weak areas and 30% to advancing strong areas. Take quizzes regularly to track progress.
    """
    
    return recommendations.strip()