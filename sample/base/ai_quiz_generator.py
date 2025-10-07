import google.generativeai as genai
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import json
import os
from django.conf import settings

class AIQuizGenerator:
    def __init__(self):
        genai.configure(api_key="AIzaSyAr4zAzbPoB7UCzA9N8BwJCq5CQYMZQPFk")
        self.model = genai.GenerativeModel('gemini-2.5-pro')
    
    def generate_quiz_content(self, topic, subtopic, difficulty, num_questions):
        """Generate quiz questions using Gemini AI"""
        prompt = f"""
        Generate {num_questions} multiple choice questions about {topic} - {subtopic}.
        Difficulty level: {difficulty}
        
        Format each question as JSON with this structure:
        {{
            "question": "Question text",
            "options": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"],
            "correct_answer": "A"
        }}
        
        Return only a JSON array of questions. Make questions {difficulty.lower()} level.
        """
        
        try:
            print(f"DEBUG: Generating content for {topic} - {subtopic}")
            response = self.model.generate_content(prompt)
            print(f"DEBUG: Raw response: {response.text[:200]}...")
            
            questions_text = response.text.strip()
            
            # Clean up response
            if questions_text.startswith('```json'):
                questions_text = questions_text[7:]
            if questions_text.endswith('```'):
                questions_text = questions_text[:-3]
            
            print(f"DEBUG: Cleaned text: {questions_text[:200]}...")
            questions = json.loads(questions_text)
            print(f"DEBUG: Parsed {len(questions)} questions")
            return questions
        except json.JSONDecodeError as e:
            print(f"JSON Error: {e}")
            print(f"Raw text: {questions_text}")
            return []
        except Exception as e:
            print(f"Error generating quiz: {e}")
            print(f"Error type: {type(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    def create_pdf(self, questions, topic, subtopic, difficulty, filename):
        """Create PDF from generated questions"""
        doc = SimpleDocTemplate(filename, pagesize=letter)
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
        
        title = Paragraph(f"{topic} - {subtopic} Quiz ({difficulty})", title_style)
        story.append(title)
        story.append(Spacer(1, 20))
        
        # Questions
        for i, q in enumerate(questions, 1):
            # Question
            question_style = ParagraphStyle(
                'Question',
                parent=styles['Normal'],
                fontSize=12,
                spaceAfter=10,
                fontName='Helvetica-Bold'
            )
            
            question_text = Paragraph(f"Q{i}. {q['question']}", question_style)
            story.append(question_text)
            
            # Options
            for option in q['options']:
                option_para = Paragraph(f"   {option}", styles['Normal'])
                story.append(option_para)
            
            story.append(Spacer(1, 15))
        
        # Answer key
        story.append(Spacer(1, 30))
        answer_title = Paragraph("Answer Key:", styles['Heading2'])
        story.append(answer_title)
        
        for i, q in enumerate(questions, 1):
            answer_text = Paragraph(f"Q{i}: {q['correct_answer']}", styles['Normal'])
            story.append(answer_text)
        
        doc.build(story)
        return filename