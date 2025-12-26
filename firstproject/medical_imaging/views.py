from django.shortcuts import render

# Create your views here.
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework. response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Count, Q, Max

from .models import Hospital, Patient, ImagingStudy, DicomImage, Diagnosis, AuditLog, ContactMessage
from .serializers import (
    HospitalSerializer,
    PatientListSerializer,
    PatientDetailSerializer,
    ImagingStudyListSerializer,
    ImagingStudyDetailSerializer,
    DicomImageSerializer,
    DiagnosisSerializer,
    AuditLogSerializer,
    ContactMessageSerializer
)


class HospitalViewSet(viewsets.ModelViewSet):
    """
    API endpoints for hospitals
    list: GET /api/hospitals/
    create: POST /api/hospitals/
    retrieve: GET /api/hospitals/{id}/
    update: PUT /api/hospitals/{id}/
    destroy: DELETE /api/hospital/{id}/
    """
    queryset = Hospital.objects.all()
    serializer_class = HospitalSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'contact_email']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']


class PatientViewSet(viewsets.ModelViewSet):
    """
    API endpoint for patients
    Uses different serilizers for list vs details views
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
    
    @action(detail=True, methods=['get'])
    def studies(self, request, pk=None):
        """Custom endpoint: GET /api/patients/{id}/studies
        Returns all imaging studies for a patient
        """
        patient = self.get_object()
        studies = patient.imaging_studies.all()
        serializer = ImagingStudyListSerializer(studies, many=True)
        return Response(serializer.data)


class ImagingStudyViewSet(viewsets.ModelViewSet):
      """
      API endpoint for imaging studies
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

      @action(detail=False, methods=['get'])
      def pending(self, request):
          """
          Custom endpoint: GET /api/studies/pending/
          Returns studies pending review
          """
          pending_studies = self.queryset.filter(status='pending')
          serializer = self.get_serializer(pending_studies, many=True)
          return Response(serializer.data)

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

      @action(detail=True, methods=['post'])
      def upload_images(self, request, pk=None):
          """
          Custom endpoint: POST /api/studies/{id}/upload_images/
          Upload medical images to a study
          Accepts multiple image files (DICOM or regular images)
          Automatically parses DICOM metadata if file is DICOM format
          """
          from .dicom_service import DicomParsingService
          from .image_cache_service import ImageCacheService
          import tempfile
          import os

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

          created_images = []
          skipped_images = []

          for idx, file in enumerate(files, start=max_instance + 1):
              # Check if file is DICOM
              is_dicom = DicomParsingService.is_dicom_file(file)

              image_data = {
                  'study': study.id,
                  'image_file': file,
                  'instance_number': idx,
                  'is_dicom': is_dicom,
              }

              # Parse DICOM metadata if it's a DICOM file
              if is_dicom:
                  try:
                      # Reset file pointer
                      file.seek(0)

                      # Parse DICOM
                      dicom_dataset, metadata = DicomParsingService.parse_dicom_file(file)

                      if dicom_dataset and metadata:
                          # Check for duplicate SOP Instance UID
                          sop_uid = str(dicom_dataset.get('SOPInstanceUID', ''))
                          if sop_uid:
                              existing_image = DicomImage.objects.filter(sop_instance_uid=sop_uid).first()
                              if existing_image:
                                  skipped_images.append({
                                      'filename': file.name,
                                      'reason': 'Duplicate SOP Instance UID',
                                      'sop_instance_uid': sop_uid
                                  })
                                  print(f"Skipping duplicate DICOM file: {file.name} (SOP UID: {sop_uid})")
                                  continue

                          # Extract key DICOM fields
                          image_data.update({
                              'slice_thickness': metadata['spatial']['slice_thickness'],
                              'pixel_spacing': str(metadata['spatial']['pixel_spacing']),
                              'slice_location': metadata['spatial']['slice_location'],
                              'rows': metadata['image']['rows'],
                              'columns': metadata['image']['columns'],
                              'bits_allocated': metadata['image']['bits_allocated'],
                              'bits_stored': metadata['image']['bits_stored'],
                              'window_center': str(metadata['display']['window_center']),
                              'window_width': str(metadata['display']['window_width']),
                              'rescale_intercept': metadata['display']['rescale_intercept'],
                              'rescale_slope': metadata['display']['rescale_slope'],
                              'manufacturer': metadata['equipment']['manufacturer'],
                              'manufacturer_model': metadata['equipment']['model'],
                              'sop_instance_uid': sop_uid,
                              'dicom_metadata': metadata,
                          })

                          # Convert DICOM to PIL Image and save as JPEG for web display
                          pil_image = DicomParsingService.dicom_to_pil_image(dicom_dataset)

                          if pil_image:
                              # Save as JPEG in temp file
                              with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                                  pil_image.save(temp_file, 'JPEG', quality=90)
                                  temp_path = temp_file.name

                              # Read back and update image_file
                              with open(temp_path, 'rb') as f:
                                  from django.core.files import File
                                  image_data['image_file'] = File(f, name=f"{file.name}.jpg")

                                  # Create image with DICOM metadata
                                  serializer = DicomImageSerializer(data=image_data, context={'request': request})
                                  if serializer.is_valid():
                                      image = serializer.save()
                                      output_serializer = DicomImageSerializer(image, context={'request': request})
                                      created_images.append(output_serializer.data)
                                  else:
                                      print(f"Serializer validation errors: {serializer.errors}")
                                      return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

                              # Clean up temp file
                              os.unlink(temp_path)
                              continue

                  except Exception as e:
                      print(f"DICOM parsing error: {str(e)}")
                      # Fall through to regular image processing

              # Regular image processing (non-DICOM or DICOM parse failed)
              file.seek(0)  # Reset file pointer
              serializer = DicomImageSerializer(data=image_data, context={'request': request})
              if serializer.is_valid():
                  image = serializer.save()
                  output_serializer = DicomImageSerializer(image, context={'request': request})
                  created_images.append(output_serializer.data)
              else:
                  print(f"Serializer validation errors: {serializer.errors}")
                  return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

          response_data = {
              'message': f'{len(created_images)} image(s) uploaded successfully',
              'images': created_images
          }

          if skipped_images:
              response_data['skipped'] = skipped_images
              response_data['message'] = f'{len(created_images)} image(s) uploaded successfully, {len(skipped_images)} skipped (duplicates)'

          return Response(response_data, status=status.HTTP_201_CREATED)


class DicomImageViewSet(viewsets.ModelViewSet):
      """
      API endpoint for DICOM images
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


class DiagnosisViewSet(viewsets.ModelViewSet):
      """
      API endpoint for diagnoses
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


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
      """
      API endpoint for audit logs (read-only for compliance)
      
      list:     GET /api/audit-logs/
      retrieve: GET /api/audit-logs/{id}/
      """
      queryset = AuditLog.objects.select_related('user').all()
      serializer_class = AuditLogSerializer
      permission_classes = [permissions.IsAuthenticated]
      filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
      filterset_fields = ['user', 'action', 'resource_type']
      search_fields = ['resource_type', 'ip_address']
      ordering_fields = ['timestamp']
      ordering = ['-timestamp']


class ContactMessageViewSet(viewsets.ModelViewSet):
    """
    API endpoint for contact form submissions
    Publicly accessible (no authentication required)
    Only allows creating new messages, not viewing/editing
    No authentication required - public endpoint
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


@api_view(['GET'])
@permission_classes([AllowAny])
def modality_distribution(request):
    """Get distribution of studies by modality"""
    from django.db.models import Count

    distribution = ImagingStudy.objects.values('modality').annotate(
        count=Count('id')
    ).order_by('-count')

    return Response(list(distribution))


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