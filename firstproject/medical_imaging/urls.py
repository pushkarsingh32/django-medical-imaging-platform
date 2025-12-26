from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    HospitalViewSet,
    PatientViewSet,
    ImagingStudyViewSet,
    DicomImageViewSet,
    DiagnosisViewSet,
    AuditLogViewSet,
    ContactMessageViewSet
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
    path('', include(router.urls))
]
