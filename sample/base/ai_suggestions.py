from django.db.models import Avg, Count
from .models import QuizAttempt

def get_ai_suggestions(user):
    """Generate AI-powered suggestions based on user performance"""
    suggestions = []
    
    # Get user's quiz attempts grouped by topic and difficulty
    attempts = QuizAttempt.objects.filter(user=user).values('topic', 'difficulty').annotate(
        count=Count('id'),
        avg_score=Avg('score')
    )
    
    # Group by topic (normalize case)
    topic_data = {}
    for attempt in attempts:
        topic = attempt['topic'].title()  # Normalize case: Java, JAVA -> Java
        difficulty = attempt['difficulty']
        count = attempt['count']
        avg_score = attempt['avg_score']
        
        if topic not in topic_data:
            topic_data[topic] = {}
        
        topic_data[topic][difficulty] = {
            'count': count,
            'avg_score': avg_score
        }
    
    # Generate ONE suggestion per topic based on highest difficulty with sufficient attempts
    processed_topics = set()
    for topic, difficulties in topic_data.items():
        if topic in processed_topics:
            continue
        processed_topics.add(topic)
        
        # Find the highest difficulty with sufficient data
        best_suggestion = None
        
        # Check Hard first (highest priority)
        if 'Hard' in difficulties and difficulties['Hard']['count'] >= 2:
            hard_data = difficulties['Hard']
            if hard_data['avg_score'] >= 80:
                best_suggestion = {
                    'type': 'new_topic',
                    'icon': '🎯',
                    'title': f'{topic} Mastered!',
                    'message': f'Outstanding! {hard_data["avg_score"]:.1f}% average. Explore new topics!',
                    'action': f'Explore New Topics',
                    'topic': 'Python' if topic != 'Python' else 'JavaScript',
                    'difficulty': 'Easy',
                    'priority': 'high'
                }
            else:
                best_suggestion = {
                    'type': 'improve',
                    'icon': '🚀',
                    'title': f'Master {topic} Hard',
                    'message': f'{hard_data["avg_score"]:.1f}% average. Aim for 80% to master this topic!',
                    'action': f'Continue {topic} Hard',
                    'topic': topic,
                    'difficulty': 'Hard',
                    'priority': 'high'
                }
        
        # Check Medium if no Hard suggestion
        elif 'Medium' in difficulties and difficulties['Medium']['count'] >= 2:
            medium_data = difficulties['Medium']
            if medium_data['avg_score'] >= 75:
                best_suggestion = {
                    'type': 'level_up',
                    'icon': '🚀',
                    'title': f'Ready for {topic} Hard!',
                    'message': f'Great! {medium_data["avg_score"]:.1f}% average. Challenge yourself with Hard!',
                    'action': f'Take {topic} Hard',
                    'topic': topic,
                    'difficulty': 'Hard',
                    'priority': 'high'
                }
            else:
                best_suggestion = {
                    'type': 'improve',
                    'icon': '💪',
                    'title': f'Improve {topic} Medium',
                    'message': f'{medium_data["avg_score"]:.1f}% average. Aim for 75% to unlock Hard!',
                    'action': f'Continue {topic} Medium',
                    'topic': topic,
                    'difficulty': 'Medium',
                    'priority': 'medium'
                }
        
        # Check Easy if no Medium/Hard suggestion
        elif 'Easy' in difficulties:
            easy_data = difficulties['Easy']
            if easy_data['count'] >= 3 and easy_data['avg_score'] >= 80:
                best_suggestion = {
                    'type': 'level_up',
                    'icon': '📈',
                    'title': f'Ready for {topic} Medium!',
                    'message': f'Excellent! {easy_data["avg_score"]:.1f}% average. Time for Medium!',
                    'action': f'Take {topic} Medium',
                    'topic': topic,
                    'difficulty': 'Medium',
                    'priority': 'high'
                }
            else:
                best_suggestion = {
                    'type': 'continue',
                    'icon': '🎯',
                    'title': f'Continue {topic} Journey',
                    'message': f'{easy_data["count"]} quiz(s) completed. Take more to unlock level up!',
                    'action': f'Continue {topic} Easy',
                    'topic': topic,
                    'difficulty': 'Easy',
                    'priority': 'medium'
                }
        
        if best_suggestion:
            suggestions.append(best_suggestion)
    
    # Always show suggestions for beginners or when no specific suggestions
    if not suggestions:
        total_attempts = QuizAttempt.objects.filter(user=user).count()
        if total_attempts == 0:
            suggestions.append({
                'type': 'start',
                'icon': '🚀',
                'title': 'Start Your Learning Journey!',
                'message': 'Welcome! Take your first quiz to begin getting personalized AI recommendations.',
                'action': 'Take First Quiz',
                'topic': 'Python',
                'difficulty': 'Easy',
                'priority': 'high'
            })
        else:
            suggestions.append({
                'type': 'explore',
                'icon': '🌟',
                'title': 'Explore New Topics!',
                'message': f'You\'ve completed {total_attempts} quiz(s). Try different topics to get more suggestions!',
                'action': 'Explore Topics',
                'topic': 'Java',
                'difficulty': 'Easy',
                'priority': 'medium'
            })
    
    # Always ensure at least one suggestion exists
    if not suggestions:
        suggestions.append({
            'type': 'general',
            'icon': '📚',
            'title': 'Keep Learning!',
            'message': 'Continue taking quizzes to improve your skills and unlock new challenges.',
            'action': 'Take Quiz',
            'topic': 'Python',
            'difficulty': 'Easy',
            'priority': 'low'
        })
    
    # Sort by priority
    priority_order = {'high': 3, 'medium': 2, 'low': 1}
    suggestions.sort(key=lambda x: priority_order.get(x['priority'], 0), reverse=True)
    
    return suggestions[:4]  # Return top 4 suggestions