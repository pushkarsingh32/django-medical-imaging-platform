from django.shortcuts import render

# Create your views here.
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Count, Q, Max
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from .models import Hospital, Patient, ImagingStudy, DicomImage, Diagnosis, AuditLog, ContactMessage, TaskStatus
from .serializers import (
    HospitalSerializer,
    PatientListSerializer,
    PatientDetailSerializer,
    ImagingStudyListSerializer,
    ImagingStudyDetailSerializer,
    DicomImageSerializer,
    DiagnosisSerializer,
    AuditLogSerializer,
    ContactMessageSerializer,
    TaskStatusSerializer
)


@extend_schema_view(
    list=extend_schema(
        tags=['Hospitals'],
        summary='List all hospitals',
        description='Retrieve a list of all hospitals with optional search and ordering.',
        parameters=[
            OpenApiParameter('search', OpenApiTypes.STR, description='Search by hospital name or contact email'),
            OpenApiParameter('ordering', OpenApiTypes.STR, description='Order by: name, created_at, -name, -created_at'),
        ]
    ),
    create=extend_schema(
        tags=['Hospitals'],
        summary='Create a new hospital',
        description='Register a new hospital in the system.'
    ),
    retrieve=extend_schema(
        tags=['Hospitals'],
        summary='Get hospital details',
        description='Retrieve detailed information about a specific hospital including patient count.'
    ),
    update=extend_schema(
        tags=['Hospitals'],
        summary='Update hospital information',
        description='Update all fields of a hospital.'
    ),
    partial_update=extend_schema(
        tags=['Hospitals'],
        summary='Partially update hospital',
        description='Update specific fields of a hospital.'
    ),
    destroy=extend_schema(
        tags=['Hospitals'],
        summary='Delete hospital',
        description='Remove a hospital from the system.'
    ),
)
class HospitalViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing hospitals and healthcare facilities.

    Provides CRUD operations for hospital management including:
    - Creating new hospitals
    - Listing and searching hospitals
    - Updating hospital information
    - Deleting hospitals
    """
    queryset = Hospital.objects.all()
    serializer_class = HospitalSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'contact_email']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']


@extend_schema_view(
    list=extend_schema(
        tags=['Patients'],
        summary='List all patients',
        description='Retrieve a paginated list of patients with filtering and search capabilities.',
        parameters=[
            OpenApiParameter('hospital', OpenApiTypes.INT, description='Filter by hospital ID'),
            OpenApiParameter('gender', OpenApiTypes.STR, description='Filter by gender (M/F/O)'),
            OpenApiParameter('search', OpenApiTypes.STR, description='Search by name, medical record number, or email'),
            OpenApiParameter('ordering', OpenApiTypes.STR, description='Order by: last_name, created_at, date_of_birth (prefix with - for descending)'),
        ]
    ),
    create=extend_schema(
        tags=['Patients'],
        summary='Create a new patient',
        description='Register a new patient in the system with their demographic and medical information.'
    ),
    retrieve=extend_schema(
        tags=['Patients'],
        summary='Get patient details',
        description='Retrieve detailed information about a specific patient including all imaging studies.'
    ),
    update=extend_schema(
        tags=['Patients'],
        summary='Update patient information',
        description='Update all fields of a patient record.'
    ),
    partial_update=extend_schema(
        tags=['Patients'],
        summary='Partially update patient',
        description='Update specific fields of a patient record.'
    ),
    destroy=extend_schema(
        tags=['Patients'],
        summary='Delete patient',
        description='Remove a patient from the system.'
    ),
)
class PatientViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing patient records.

    Provides comprehensive patient management including:
    - Patient demographics and contact information
    - Medical record tracking
    - Associated imaging studies
    - Filtering by hospital and gender
    - Full-text search across patient fields
    """
    queryset = Patient.objects.select_related('hospital').all()
    permission_classes= [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['hospital', 'gender']
    search_fields = ['first_name', 'last_name', 'medical_record_number', 'email']
    ordering_fields = ['last_name', 'created_at', 'date_of_birth']

    def get_serializer_class(self):
        """Use Detailed serilizer for single patient view"""
        if self.action == 'retrieve':
            return PatientDetailSerializer
        return PatientListSerializer

    @extend_schema(
        tags=['Patients'],
        summary='Get patient studies',
        description='Retrieve all imaging studies for a specific patient.',
        responses={200: ImagingStudyListSerializer(many=True)}
    )
    @action(detail=True, methods=['get'])
    def studies(self, request, pk=None):
        """Custom endpoint: GET /api/patients/{id}/studies
        Returns all imaging studies for a patient
        """
        patient = self.get_object()
        studies = patient.imaging_studies.all()
        serializer = ImagingStudyListSerializer(studies, many=True)
        return Response(serializer.data)

    @extend_schema(
        tags=['Patients'],
        summary='Generate patient PDF report',
        description='Generate a comprehensive PDF report for a patient including all studies and diagnoses. Returns task_id for async processing.',
        responses={202: OpenApiTypes.OBJECT}
    )
    @action(detail=True, methods=['post'])
    def generate_report(self, request, pk=None):
        """
        Custom endpoint: POST /api/patients/{id}/generate_report/
        Generates a comprehensive PDF report for the patient asynchronously
        Returns task_id for progress tracking
        """
        from .tasks import generate_patient_report_async

        patient = self.get_object()
        user_id = request.user.id if request.user.is_authenticated else None

        # Dispatch async task
        task = generate_patient_report_async.delay(patient.id, user_id)

        return Response({
            'message': 'Generating PDF report...',
            'task_id': task.id,
            'patient_id': patient.id,
            'patient_name': patient.full_name,
            'status': 'processing'
        }, status=status.HTTP_202_ACCEPTED)


@extend_schema_view(
    list=extend_schema(
        tags=['Studies'],
        summary='List all imaging studies',
        description='Retrieve a paginated list of imaging studies with filtering and search.',
        parameters=[
            OpenApiParameter('patient', OpenApiTypes.INT, description='Filter by patient ID'),
            OpenApiParameter('modality', OpenApiTypes.STR, description='Filter by modality (CT, MRI, XRAY, US, PET, MAMMO)'),
            OpenApiParameter('status', OpenApiTypes.STR, description='Filter by status (pending, in_progress, completed)'),
            OpenApiParameter('body_part', OpenApiTypes.STR, description='Filter by body part'),
            OpenApiParameter('search', OpenApiTypes.STR, description='Search by patient name, MRN, body part, or clinical notes'),
            OpenApiParameter('ordering', OpenApiTypes.STR, description='Order by: study_date, created_at (prefix with - for descending)'),
        ]
    ),
    create=extend_schema(
        tags=['Studies'],
        summary='Create a new imaging study',
        description='Create a new imaging study for a patient.'
    ),
    retrieve=extend_schema(
        tags=['Studies'],
        summary='Get study details',
        description='Retrieve detailed information about a specific study including images and diagnosis.'
    ),
    update=extend_schema(
        tags=['Studies'],
        summary='Update study information',
        description='Update all fields of an imaging study.'
    ),
    partial_update=extend_schema(
        tags=['Studies'],
        summary='Partially update study',
        description='Update specific fields of an imaging study.'
    ),
    destroy=extend_schema(
        tags=['Studies'],
        summary='Delete study',
        description='Remove an imaging study from the system.'
    ),
)
class ImagingStudyViewSet(viewsets.ModelViewSet):
      """
      ViewSet for managing medical imaging studies.

      Provides comprehensive study management including:
      - CT, MRI, X-Ray, Ultrasound, PET, and Mammography studies
      - DICOM and standard image support
      - Study status tracking (pending, in progress, completed)
      - Associated patient and hospital information
      - Image upload and management
      - Radiological diagnosis integration
      """
      queryset = ImagingStudy.objects.select_related('patient',
  'patient__hospital').prefetch_related('images', 'diagnosis').all()
      permission_classes = [permissions.IsAuthenticated]
      filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
      filterset_fields = ['patient', 'modality', 'status', 'body_part']
      search_fields = ['patient__first_name', 'patient__last_name',
  'patient__medical_record_number', 'body_part', 'clinical_notes']
      ordering_fields = ['study_date', 'created_at']
      ordering = ['-study_date']

      def get_serializer_class(self):
          """Use detailed serializer for single study view"""
          if self.action == 'retrieve':
              return ImagingStudyDetailSerializer
          return ImagingStudyListSerializer

      @extend_schema(
          tags=['Studies'],
          summary='Get pending studies',
          description='Retrieve all studies with pending status awaiting review.',
          responses={200: ImagingStudyListSerializer(many=True)}
      )
      @action(detail=False, methods=['get'])
      def pending(self, request):
          """
          Custom endpoint: GET /api/studies/pending/
          Returns studies pending review
          """
          pending_studies = self.queryset.filter(status='pending')
          serializer = self.get_serializer(pending_studies, many=True)
          return Response(serializer.data)

      @extend_schema(
          tags=['Statistics'],
          summary='Get study statistics',
          description='Retrieve summary statistics including total studies, status breakdown, and modality distribution.',
          responses={200: OpenApiTypes.OBJECT}
      )
      @action(detail=False, methods=['get'])
      def statistics(self, request):
          """
          Custom endpoint: GET /api/studies/statistics/
          Returns summary statistics
          """
          stats = {
              'total_studies': self.queryset.count(),
              'pending': self.queryset.filter(status='pending').count(),
              'in_progress': self.queryset.filter(status='in_progress').count(),
              'completed': self.queryset.filter(status='completed').count(),
              'by_modality': list(
                  self.queryset.values('modality').annotate(count=Count('id')).order_by('-count')
              ),
          }
          return Response(stats)

      @extend_schema(
          tags=['Diagnoses'],
          summary='Add diagnosis to study',
          description='Create a new diagnosis for an imaging study. Study must not already have a diagnosis.',
          responses={201: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT}
      )
      @action(detail=True, methods=['post'])
      def diagnosis(self, request, pk=None):
          """
          Custom endpoint: POST /api/studies/{id}/diagnosis/
          Add a diagnosis to a study
          """
          study = self.get_object()

          # Check if diagnosis already exists (OneToOneField)
          if hasattr(study, 'diagnosis') and study.diagnosis:
              return Response(
                  {'error': 'This study already has a diagnosis. Use PUT to update it.'},
                  status=status.HTTP_400_BAD_REQUEST
              )

          serializer = DiagnosisSerializer(data=request.data)

          if serializer.is_valid():
              serializer.save(study=study, radiologist=request.user)
              return Response(serializer.data, status=status.HTTP_201_CREATED)

          print(f"Diagnosis validation errors: {serializer.errors}")
          return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

      @extend_schema(
          tags=['Images'],
          summary='Upload images to study',
          description='Upload multiple DICOM or standard medical images to a study. DICOM files are automatically parsed for metadata. Duplicate DICOM files (same SOP Instance UID) are skipped.',
          request={
              'multipart/form-data': {
                  'type': 'object',
                  'properties': {
                      'images': {
                          'type': 'array',
                          'items': {'type': 'string', 'format': 'binary'},
                          'description': 'One or more image files (DICOM or JPEG/PNG)'
                      }
                  }
              }
          },
          responses={
              201: {
                  'type': 'object',
                  'properties': {
                      'message': {'type': 'string'},
                      'images': {'type': 'array'},
                      'skipped': {
                          'type': 'array',
                          'items': {
                              'type': 'object',
                              'properties': {
                                  'filename': {'type': 'string'},
                                  'reason': {'type': 'string'},
                                  'sop_instance_uid': {'type': 'string'}
                              }
                          }
                      }
                  }
              }
          }
      )
      @action(detail=True, methods=['post'])
      def upload_images(self, request, pk=None):
          """
          Custom endpoint: POST /api/studies/{id}/upload_images/
          Upload medical images to a study - processes asynchronously with Celery
          Accepts multiple image files (DICOM or regular images)
          Returns task_id for progress tracking
          """
          from .tasks import process_dicom_images_async

          study = self.get_object()
          files = request.FILES.getlist('images')

          if not files:
              return Response(
                  {'error': 'No images provided'},
                  status=status.HTTP_400_BAD_REQUEST
              )

          # Get the highest existing instance_number for this study
          max_instance_result = study.images.aggregate(Max('instance_number'))
          max_instance = max_instance_result['instance_number__max'] or 0

          # Prepare file data for Celery task
          file_data_list = []
          for idx, file in enumerate(files, start=max_instance + 1):
              # Read file content into memory
              file.seek(0)
              content = file.read()

              file_data_list.append({
                  'filename': file.name,
                  'content': content,
                  'instance_number': idx,
              })

          # Dispatch async task
          user_id = request.user.id if request.user.is_authenticated else None
          task = process_dicom_images_async.delay(study.id, file_data_list, user_id)

          return Response({
              'message': f'Processing {len(files)} image(s) in background',
              'task_id': task.id,
              'total_files': len(files),
              'status': 'processing'
          }, status=status.HTTP_202_ACCEPTED)


@extend_schema_view(
    list=extend_schema(
        tags=['Images'],
        summary='List all medical images',
        description='Retrieve a list of DICOM and standard medical images with filtering by study.',
        parameters=[
            OpenApiParameter('study', OpenApiTypes.INT, description='Filter by study ID'),
            OpenApiParameter('ordering', OpenApiTypes.STR, description='Order by: instance_number, uploaded_at (prefix with - for descending)'),
        ]
    ),
    create=extend_schema(
        tags=['Images'],
        summary='Upload a single image',
        description='Upload a single DICOM or standard medical image. For multiple uploads, use the study upload endpoint.'
    ),
    retrieve=extend_schema(
        tags=['Images'],
        summary='Get image details',
        description='Retrieve detailed information about a specific medical image including DICOM metadata if available.'
    ),
    update=extend_schema(
        tags=['Images'],
        summary='Update image metadata',
        description='Update image metadata and information.'
    ),
    partial_update=extend_schema(
        tags=['Images'],
        summary='Partially update image',
        description='Update specific fields of an image.'
    ),
    destroy=extend_schema(
        tags=['Images'],
        summary='Delete image',
        description='Remove an image from the system.'
    ),
)
class DicomImageViewSet(viewsets.ModelViewSet):
      """
      ViewSet for managing medical images.

      Supports both DICOM and standard image formats including:
      - DICOM file parsing with automatic metadata extraction
      - SOP Instance UID tracking for DICOM compliance
      - Progressive image loading (thumbnails and full resolution)
      - Image metadata including window/level, slice location
      - Equipment and acquisition parameters
      """
      queryset = DicomImage.objects.select_related('study', 'study__patient').all()
      serializer_class = DicomImageSerializer
      permission_classes = [permissions.IsAuthenticated]
      filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
      filterset_fields = ['study']
      ordering_fields = ['instance_number', 'uploaded_at']
      ordering = ['instance_number']

      def perform_create(self, serializer):
          """Automatically calculate file size when uploading"""
          instance = serializer.save()
          if instance.image_file:
              instance.file_size_bytes = instance.image_file.size
              instance.save()


@extend_schema_view(
    list=extend_schema(
        tags=['Diagnoses'],
        summary='List all diagnoses',
        description='Retrieve a list of radiological diagnoses with filtering and search.',
        parameters=[
            OpenApiParameter('severity', OpenApiTypes.STR, description='Filter by severity (low, moderate, high, critical)'),
            OpenApiParameter('radiologist', OpenApiTypes.INT, description='Filter by radiologist user ID'),
            OpenApiParameter('search', OpenApiTypes.STR, description='Search by findings, impression, or recommendations'),
            OpenApiParameter('ordering', OpenApiTypes.STR, description='Order by: diagnosed_at, severity (prefix with - for descending)'),
        ]
    ),
    create=extend_schema(
        tags=['Diagnoses'],
        summary='Create a diagnosis',
        description='Create a new radiological diagnosis for a study. Automatically sets the radiologist to the current user and updates study status to completed.'
    ),
    retrieve=extend_schema(
        tags=['Diagnoses'],
        summary='Get diagnosis details',
        description='Retrieve detailed information about a specific diagnosis.'
    ),
    update=extend_schema(
        tags=['Diagnoses'],
        summary='Update diagnosis',
        description='Update all fields of a diagnosis.'
    ),
    partial_update=extend_schema(
        tags=['Diagnoses'],
        summary='Partially update diagnosis',
        description='Update specific fields of a diagnosis.'
    ),
    destroy=extend_schema(
        tags=['Diagnoses'],
        summary='Delete diagnosis',
        description='Remove a diagnosis from the system.'
    ),
)
class DiagnosisViewSet(viewsets.ModelViewSet):
      """
      ViewSet for managing radiological diagnoses.

      Provides diagnosis management including:
      - Radiological findings and impressions
      - Severity classification (low, moderate, high, critical)
      - Treatment recommendations
      - Automatic study completion tracking
      - Radiologist attribution
      """
      queryset = Diagnosis.objects.select_related('study', 'study__patient', 'radiologist').all()
      serializer_class = DiagnosisSerializer
      permission_classes = [permissions.IsAuthenticated]
      filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
      filterset_fields = ['severity', 'radiologist']
      search_fields = ['findings', 'impression', 'recommendations']
      ordering_fields = ['diagnosed_at', 'severity']
      ordering = ['-diagnosed_at']

      def perform_create(self, serializer):
          """Automatically set radiologist to current user and update study status"""
          diagnosis = serializer.save(radiologist=self.request.user)
          # Update study status to completed
          diagnosis.study.status = 'completed'
          diagnosis.study.save()


@extend_schema_view(
    list=extend_schema(
        tags=['Audit'],
        summary='List audit logs',
        description='Retrieve read-only audit logs for compliance and security tracking.',
        parameters=[
            OpenApiParameter('user', OpenApiTypes.INT, description='Filter by user ID'),
            OpenApiParameter('action', OpenApiTypes.STR, description='Filter by action type'),
            OpenApiParameter('resource_type', OpenApiTypes.STR, description='Filter by resource type'),
            OpenApiParameter('search', OpenApiTypes.STR, description='Search by resource type or IP address'),
            OpenApiParameter('ordering', OpenApiTypes.STR, description='Order by: timestamp (prefix with - for descending)'),
        ]
    ),
    retrieve=extend_schema(
        tags=['Audit'],
        summary='Get audit log details',
        description='Retrieve detailed information about a specific audit log entry.'
    ),
)
class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
      """
      Read-only ViewSet for audit logs.

      Provides compliance and security tracking including:
      - User actions and timestamps
      - Resource access tracking
      - IP address logging
      - Read-only access for data integrity
      """
      queryset = AuditLog.objects.select_related('user').all()
      serializer_class = AuditLogSerializer
      permission_classes = [permissions.IsAuthenticated]
      filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
      filterset_fields = ['user', 'action', 'resource_type']
      search_fields = ['resource_type', 'ip_address']
      ordering_fields = ['timestamp']
      ordering = ['-timestamp']


@extend_schema_view(
    create=extend_schema(
        tags=['Contact'],
        summary='Submit contact form',
        description='Public endpoint for contact form submissions. No authentication required.',
        responses={
            201: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': {'type': 'object'}
                }
            }
        }
    ),
)
class ContactMessageViewSet(viewsets.ModelViewSet):
    """
    Public ViewSet for contact form submissions.

    This endpoint allows users to submit contact messages without authentication.
    Only POST requests are allowed for privacy and security.
    """
    queryset = ContactMessage.objects.all()
    serializer_class = ContactMessageSerializer
    permission_classes = [permissions.IsAuthenticated]  # Public endpoint
    authentication_classes = []  # Disable authentication (and CSRF) for this endpoint
    http_method_names = ['post']  # Only allow POST requests

    def create(self, request, *args, **kwargs):
        """Create a new contact message"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        return Response(
            {
                'success': True,
                'message': 'Thank you for contacting us! We will get back to you soon.',
                'data': serializer.data
            },
            status=status.HTTP_201_CREATED
        )


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from datetime import timedelta


@extend_schema(
    tags=['Statistics'],
    summary='Get dashboard statistics',
    description='Retrieve overall system statistics including patient count, study count, and recent activity metrics.',
    responses={
        200: {
            'type': 'object',
            'properties': {
                'total_patients': {'type': 'integer'},
                'total_studies': {'type': 'integer'},
                'total_images': {'type': 'integer'},
                'total_hospitals': {'type': 'integer'},
                'new_patients_this_month': {'type': 'integer'},
                'studies_this_week': {'type': 'integer'},
            }
        }
    }
)
@api_view(['GET'])
@permission_classes([AllowAny])
def dashboard_stats(request):
    """Get dashboard statistics"""
    from datetime import date
    today = date.today()
    first_day_of_month = today.replace(day=1)
    week_ago = today - timedelta(days=7)

    stats = {
        'total_patients': Patient.objects.count(),
        'total_studies': ImagingStudy.objects.count(),
        'total_images': DicomImage.objects.count(),
        'total_hospitals': Hospital.objects.count(),
        'new_patients_this_month': Patient.objects.filter(created_at__gte=first_day_of_month).count(),
        'studies_this_week': ImagingStudy.objects.filter(created_at__gte=week_ago).count(),
    }
    return Response(stats)


@extend_schema(
    tags=['Statistics'],
    summary='Get study trends',
    description='Retrieve study count trends over a specified time period.',
    parameters=[
        OpenApiParameter('days', OpenApiTypes.INT, description='Number of days to retrieve trends for (default: 30)')
    ],
    responses={
        200: {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'date': {'type': 'string', 'format': 'date'},
                    'count': {'type': 'integer'}
                }
            }
        }
    }
)
@api_view(['GET'])
@permission_classes([AllowAny])
def study_trends(request):
    """Get study trends over time"""
    days = int(request.GET.get('days', 30))
    from datetime import date
    today = date.today()
    start_date = today - timedelta(days=days)

    # Group studies by date
    trends = []
    for i in range(days):
        current_date = start_date + timedelta(days=i)
        count = ImagingStudy.objects.filter(
            study_date__date=current_date
        ).count()
        trends.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'count': count
        })

    return Response(trends)


@extend_schema(
    tags=['Statistics'],
    summary='Get modality distribution',
    description='Retrieve the distribution of studies by imaging modality.',
    responses={
        200: {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'modality': {'type': 'string'},
                    'count': {'type': 'integer'}
                }
            }
        }
    }
)
@api_view(['GET'])
@permission_classes([AllowAny])
def modality_distribution(request):
    """Get distribution of studies by modality"""
    from django.db.models import Count

    distribution = ImagingStudy.objects.values('modality').annotate(
        count=Count('id')
    ).order_by('-count')

    return Response(list(distribution))


@extend_schema(
    tags=['Statistics'],
    summary='Get recent activity',
    description='Retrieve recent study activity with patient and hospital information.',
    parameters=[
        OpenApiParameter('limit', OpenApiTypes.INT, description='Number of recent studies to retrieve (default: 10)')
    ],
    responses={
        200: {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'id': {'type': 'integer'},
                    'modality': {'type': 'string'},
                    'body_part': {'type': 'string'},
                    'patient_name': {'type': 'string'},
                    'hospital_name': {'type': 'string'},
                    'status': {'type': 'string'},
                    'study_date': {'type': 'string', 'format': 'date-time'}
                }
            }
        }
    }
)
@api_view(['GET'])
@permission_classes([AllowAny])
def recent_activity(request):
    """Get recent study activity"""
    limit = int(request.GET.get('limit', 10))

    recent_studies = ImagingStudy.objects.select_related(
        'patient', 'patient__hospital'
    ).order_by('-created_at')[:limit]

    activity = []
    for study in recent_studies:
        activity.append({
            'id': study.id,
            'modality': study.modality,
            'body_part': study.body_part,
            'patient_name': study.patient.full_name,
            'hospital_name': study.patient.hospital.name,
            'status': study.status,
            'study_date': study.study_date.isoformat(),
        })

    return Response(activity)


@extend_schema(
    tags=['Tasks'],
    summary='Get task status',
    description='Retrieve the status of an asynchronous task by task ID.',
    parameters=[
        OpenApiParameter('task_id', OpenApiTypes.STR, OpenApiParameter.PATH, description='Celery task ID'),
    ],
    responses={200: TaskStatusSerializer, 404: OpenApiTypes.OBJECT}
)
@api_view(['GET'])
@permission_classes([AllowAny])
def task_status(request, task_id):
    """Get status of a Celery task"""
    try:
        task = TaskStatus.objects.get(task_id=task_id)
        serializer = TaskStatusSerializer(task)
        return Response(serializer.data)
    except TaskStatus.DoesNotExist:
        return Response(
            {'error': 'Task not found'},
            status=status.HTTP_404_NOT_FOUND
        )