from django.contrib import admin
from django.urls import path
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import Profile, PDFUpload, QuizAttempt, UserPreferences, Achievement, GeneratedMCQ
from .views import extract_mcqs_from_pdf

@admin.register(GeneratedMCQ)
class GeneratedMCQAdmin(admin.ModelAdmin):
    list_display = ['topic', 'subtopic', 'difficulty', 'question_no', 'question', 'created_by', 'created_at']
    list_filter = ['topic', 'difficulty', 'created_by', 'created_at']
    search_fields = ['question', 'topic', 'subtopic']
    ordering = ['-created_at']

@admin.register(PDFUpload)
class PDFUploadAdmin(admin.ModelAdmin):
    list_display = ['topic', 'subtopic', 'difficulty', 'question_no', 'question', 'uploaded_at']
    list_filter = ['topic', 'difficulty', 'uploaded_at']
    change_list_template = 'pdf_upload_changelist.html'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-extract/', self.upload_extract_view, name='pdf_upload_extract'),
        ]
        return custom_urls + urls
    
    @method_decorator(csrf_exempt)
    def upload_extract_view(self, request):
        if request.method == 'POST':
            try:
                pdf_file = request.FILES.get('pdf_file')
                topic = request.POST.get('topic')
                subtopic = request.POST.get('subtopic')
                difficulty = request.POST.get('difficulty')
                
                if not all([pdf_file, topic, subtopic, difficulty]):
                    return JsonResponse({'success': False, 'error': 'All fields are required'})
                
                mcqs = extract_mcqs_from_pdf(pdf_file, topic, subtopic, difficulty)
                
                return JsonResponse({
                    'success': True, 
                    'message': f'Successfully extracted {len(mcqs)} MCQs',
                    'count': len(mcqs)
                })
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})
        
        return JsonResponse({'success': False, 'error': 'Invalid request method'})

@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ['user', 'topic', 'score', 'attempt_date']
    list_filter = ['topic', 'attempt_date']

admin.site.register(Profile)
admin.site.register(UserPreferences)
admin.site.register(Achievement)