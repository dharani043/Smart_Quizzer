"""
URL configuration for sample project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from base import views


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('adminlogin/', views.admin_login, name='adminlogin'),
    path('login/', views.user_login, name='login'),
    path('register/', views.register, name='register'),
    path('admindashboard/', views.admindashboard, name='admindashboard'),
    path('userdashboard/', views.userdashboard, name='userdashboard'),
    path('upload_mcq/', views.upload_mcq, name='upload_mcq'),
    path('logout/', views.user_logout, name='logout'),
    path('all_users/', views.all_users_view, name='all_users'),
    path('start_quiz/', views.start_quiz_view, name='start_quiz'),
    path('quiz_question/', views.quiz_question_view, name='quiz_question'),
    path('process_answer/', views.process_answer_view, name='process_answer'),
    path('progress/', views.progress_view, name='progress'),
    path('content_moderation/', views.content_moderation_view, name='content_moderation'),
    # path('topics/', views.topics_view, name='topics'),
    path('history/', views.quiz_history_view, name='history'),
    path('profile/', views.profile_view, name='profile'),
    path('settings/', views.settings_view, name='settings'),
    path('help/', views.help_view, name='help'),
    path('analytics/', views.analytics_view, name='analytics_view'),
    path('regenerate-insights/', views.regenerate_insights_view, name='regenerate_insights'),
    path('explain-insight/', views.explain_insight_view, name='explain_insight'),
    path('rate-insight/', views.rate_insight_view, name='rate_insight'),
    path('chatbot/', views.chatbot_view, name='chatbot'),
    path('chatbot/explain/', views.chatbot_explain, name='chatbot_explain'),
    path('browse-topics/', views.browse_topics_view, name='browse_topics'),
    path('learning-path/<str:path_name>/', views.learning_path_detail_view, name='learning_path_detail'),
    path('start-learning-path/<str:path_name>/', views.start_learning_path_view, name='start_learning_path'),
    path('request-topic/', views.request_topic_view, name='request_topic'),
    path('topic-requests-admin/', views.topic_requests_admin_view, name='topic_requests_admin'),
    path('reports/', views.reports_view, name='reports'),
    path('generate_ai_quiz/', views.generate_ai_quiz, name='generate_ai_quiz'),
    path('view_ai_pdfs/', views.view_ai_pdfs, name='view_ai_pdfs'),
    path('view_admin_pdfs/', views.view_admin_pdfs, name='view_admin_pdfs'),
    path('view_questions/<str:topic>/<str:subtopic>/', views.view_questions, name='view_questions'),
    path('export_admin_pdf/<str:topic>/<str:subtopic>/', views.export_admin_pdf, name='export_admin_pdf'),
    # Real-time analytics API endpoints
    path('api/real-time-analytics/', views.real_time_analytics_api, name='real_time_analytics_api'),
    path('api/user-performance/', views.user_performance_api, name='user_performance_api'),
    path('api/user-growth-data/', views.get_user_growth_data_api, name='user_growth_data_api'),
    # User management endpoints
    path('admin/edit-user/', views.edit_user_view, name='edit_user'),
    path('admin/block-user/', views.block_user_view, name='block_user'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)