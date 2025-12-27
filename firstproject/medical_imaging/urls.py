from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    HospitalViewSet,
    PatientViewSet,
    ImagingStudyViewSet,
    DicomImageViewSet,
    DiagnosisViewSet,
    AuditLogViewSet,
    ContactMessageViewSet,
    dashboard_stats,
    study_trends,
    modality_distribution,
    recent_activity,
    task_status,
)
from .ai_chat_view import chat, chat_stream
from .image_views import (
    serve_thumbnail,
    serve_preview,
    serve_webp,
    serve_full_image,
    image_metadata,
    invalidate_cache,
    cache_statistics,
)


router = DefaultRouter()
router.register(r'hospitals', HospitalViewSet, basename='hospital'),
router.register(r'patients', PatientViewSet, basename='patient')
router.register(r'studies', ImagingStudyViewSet, basename='imagingstudy')
router.register(r'images', DicomImageViewSet, basename='dicomimage')
router.register(r'diagnoses', DiagnosisViewSet, basename='diagnosis')
router.register(r'audit-logs', AuditLogViewSet, basename='auditlog')
router.register(r'contact', ContactMessageViewSet, basename='contact')


urlpatterns = [
    path('', include(router.urls)),
    # Stats endpoints
    path('stats/', dashboard_stats, name='dashboard-stats'),
    path('stats/trends/', study_trends, name='study-trends'),
    path('stats/modality-distribution/', modality_distribution, name='modality-distribution'),
    path('stats/recent-activity/', recent_activity, name='recent-activity'),
    # Task status endpoint
    path('tasks/<str:task_id>/', task_status, name='task-status'),
    # AI Chat endpoints
    path('ai/chat/', chat, name='ai-chat'),
    path('ai/chat/stream/', chat_stream, name='ai-chat-stream'),
    # Image serving endpoints with progressive loading
    path('images/<int:image_id>/thumbnail/', serve_thumbnail, name='image-thumbnail'),
    path('images/<int:image_id>/preview/', serve_preview, name='image-preview'),
    path('images/<int:image_id>/webp/', serve_webp, name='image-webp'),
    path('images/<int:image_id>/full/', serve_full_image, name='image-full'),
    path('images/<int:image_id>/metadata/', image_metadata, name='image-metadata'),
    path('images/<int:image_id>/invalidate-cache/', invalidate_cache, name='invalidate-cache'),
    path('images/cache-stats/', cache_statistics, name='cache-statistics'),
]
