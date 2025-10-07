import os
import json
import google.generativeai as genai
from datetime import datetime, timedelta
from django.db.models import Avg
from django.utils import timezone
from .models import QuizAttempt

# Configure Google Generative AI
genai.configure(api_key="AIzaSyAr4zAzbPoB7UCzA9N8BwJCq5CQYMZQPFk")
model = genai.GenerativeModel('gemini-2.5-pro')

def compute_topic_insights(user):
    """Compute structured insights from database"""
    today = timezone.now().date()
    this_month_start = today.replace(day=1)
    last_month_end = this_month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    topics = QuizAttempt.objects.filter(user=user).values_list('topic', flat=True).distinct()
    results = []
    
    for topic in topics:
        this_avg = QuizAttempt.objects.filter(
            user=user, topic=topic, attempt_date__gte=this_month_start
        ).aggregate(avg=Avg('score'))['avg'] or 0
        
        prev_avg = QuizAttempt.objects.filter(
            user=user, topic=topic, 
            attempt_date__gte=last_month_start, 
            attempt_date__lte=last_month_end
        ).aggregate(avg=Avg('score'))['avg'] or 0
        
        delta = round(this_avg - prev_avg, 1)
        
        results.append({
            "topic": topic,
            "this_avg": round(this_avg, 1),
            "prev_avg": round(prev_avg, 1),
            "delta": delta
        })
    
    return results

def generate_llm_insights(user):
    """Generate AI insights using OpenAI"""
    try:
        insights_data = compute_topic_insights(user)
        
        if not insights_data:
            return ["📊 Take more quizzes to unlock personalized AI insights!"]
        
        # Build compact data lines for LLM
        data_lines = []
        for item in insights_data:
            data_lines.append(f"{item['topic']}: this_month={item['this_avg']} prev_month={item['prev_avg']} delta={item['delta']:+.1f}")
        
        # Get completed topics
        completed_topics = [item['topic'] for item in insights_data]
        
        prompt = f"""You are a study coach. User has completed: {', '.join(completed_topics)}

Based on their quiz performance:
{chr(10).join(data_lines)}

Suggest 2 next learning steps:
1. Advanced topic in their strongest area
2. New technology that builds on what they know

Keep each under 50 words with emojis."""

        response = model.generate_content(prompt)
        
        # Split response into insights
        text = response.text.strip()
        insights = [line.strip() for line in text.split('\n') if line.strip() and not line.strip().startswith('*')]
        return insights[:2] if len(insights) >= 2 else [text]
        
    except Exception as e:
        # Fallback to simple insights if LLM fails
        return generate_fallback_insights(insights_data if 'insights_data' in locals() else [])

def generate_fallback_insights(insights_data):
    """Fallback insights if LLM fails"""
    if not insights_data:
        return ["📊 Take more quizzes to unlock personalized insights!"]
    
    import random
    insights = []
    topics = [item['topic'] for item in insights_data]
    
    # Learning progression map
    progression = {
        'Java': ['Spring Boot', 'Microservices', 'Hibernate'],
        'Python': ['Django', 'Flask', 'Machine Learning'],
        'JavaScript': ['React', 'Node.js', 'TypeScript'],
        'SQL': ['MongoDB', 'PostgreSQL', 'Database Design']
    }
    
    # Suggest next topics based on completed ones
    for topic in topics:
        if topic in progression:
            next_topics = progression[topic]
            next_topic = random.choice(next_topics)
            insights.append(f"🚀 Since you've mastered {topic}, try {next_topic} next!")
            break
    
    # If no progression found, suggest new area
    if not insights:
        all_topics = ['Python', 'React', 'AWS', 'Docker']
        new_topics = [t for t in all_topics if t not in topics]
        if new_topics:
            topic = random.choice(new_topics)
            insights.append(f"🌟 Ready for a new challenge? Try learning {topic}!")
    
    # Performance feedback
    best_topic = max(insights_data, key=lambda x: x['this_avg'])['topic']
    insights.append(f"💪 You're strongest in {best_topic}. Time for advanced concepts!")
    
    return insights[:2]