from rest_framework import serializers
from .models import Hospital, Patient, ImagingStudy, DicomImage, Diagnosis, AuditLog
from django.contrib.auth.models import User

class HospitalSerializer(serializers.ModelSerializer):
    """
    Serializer for Hospital model
    Converts Hospita objects to/from JSON
    """
    patient_count = serializers.SerializerMethodField()

    class Meta: 
        model = Hospital
        fields = [
            "id", "name", "address", "contact_email", "contact_phone", "created_at",
            "patient_count"
        ]
        read_only_fields = ['created_at']
    
    def get_patient_count(self, obj):
        """Count total patients in this hospital"""
        return obj.patients.count()
    
class PatientListSerializer(serializers.ModelSerializer):
      """
      Lightweight serializer for patient list view
      Only includes essential fields for performance
      """
      hospital_name = serializers.CharField(source='hospital.name', read_only=True)
      age = serializers.SerializerMethodField()

      class Meta:
          model = Patient
          fields = ['id', 'medical_record_number', 'first_name', 'last_name', 'full_name',
                    'date_of_birth', 'age', 'gender', 'hospital_name', 'created_at']
          read_only_fields = ['full_name', 'created_at']

      def get_age(self, obj):
          """Calculate patient age in years"""
          from datetime import date
          today = date.today()
          return today.year - obj.date_of_birth.year - (
              (today.month, today.day) < (obj.date_of_birth.month, obj.date_of_birth.day)
          )


class PatientDetailSerializer(serializers.ModelSerializer):
      """
      Detailed serializer for single patient view
      Includes related data like imaging studies count
      """
      hospital_name = serializers.CharField(source='hospital.name', read_only=True)
      age = serializers.SerializerMethodField()
      total_studies = serializers.SerializerMethodField()
      recent_studies = serializers.SerializerMethodField()

      class Meta:
          model = Patient
          fields = ['id', 'medical_record_number', 'first_name', 'last_name', 'full_name',
                    'date_of_birth', 'age', 'gender', 'phone', 'email', 'address',
                    'hospital', 'hospital_name', 'total_studies', 'recent_studies',
                    'created_at', 'updated_at']
          read_only_fields = ['full_name', 'created_at', 'updated_at']

      def get_age(self, obj):
          from datetime import date
          today = date.today()
          return today.year - obj.date_of_birth.year - (
              (today.month, today.day) < (obj.date_of_birth.month, obj.date_of_birth.day)
          )

      def get_total_studies(self, obj):
          return obj.imaging_studies.count()

      def get_recent_studies(self, obj):
          """Get 5 most recent studies"""
          recent = obj.imaging_studies.all()[:5]
          return ImagingStudyListSerializer(recent, many=True).data


class DicomImageSerializer(serializers.ModelSerializer):
      """
      Serializer for DICOM images
      """
      image_url = serializers.SerializerMethodField()

      class Meta:
          model = DicomImage
          fields = ['id', 'study', 'instance_number', 'image_file', 'image_url',
                    'slice_thickness', 'pixel_spacing', 'file_size_bytes', 'uploaded_at']
          read_only_fields = ['uploaded_at', 'file_size_bytes']

      def get_image_url(self, obj):
          """Return full URL for the image file"""
          if obj.image_file:
              request = self.context.get('request')
              if request:
                  return request.build_absolute_uri(obj.image_file.url)
          return None


class DiagnosisSerializer(serializers.ModelSerializer):
      """
      Serializer for Diagnosis
      """
      radiologist_name = serializers.CharField(source='radiologist.get_full_name', read_only=True)

      class Meta:
          model = Diagnosis
          fields = ['id', 'study', 'radiologist', 'radiologist_name', 'findings',
                    'impression', 'severity', 'recommendations', 'diagnosed_at', 'updated_at']
          read_only_fields = ['diagnosed_at', 'updated_at']


class ImagingStudyListSerializer(serializers.ModelSerializer):
      """
      Lightweight serializer for imaging study list
      """
      patient_name = serializers.CharField(source='patient.full_name', read_only=True)
      patient_mrn = serializers.CharField(source='patient.medical_record_number', read_only=True)
      image_count = serializers.SerializerMethodField()
      has_diagnosis = serializers.SerializerMethodField()

      class Meta:
          model = ImagingStudy
          fields = ['id', 'patient', 'patient_name', 'patient_mrn', 'study_date',
                    'modality', 'body_part', 'status', 'image_count', 'has_diagnosis',
  'created_at']
          read_only_fields = ['created_at']

      def get_image_count(self, obj):
          return obj.images.count()

      def get_has_diagnosis(self, obj):
          return hasattr(obj, 'diagnosis')


class ImagingStudyDetailSerializer(serializers.ModelSerializer):
      """
      Detailed serializer for single imaging study
      Includes images and diagnosis
      """
      patient_name = serializers.CharField(source='patient.full_name', read_only=True)
      patient_mrn = serializers.CharField(source='patient.medical_record_number', read_only=True)
      images = DicomImageSerializer(many=True, read_only=True)
      diagnosis = DiagnosisSerializer(read_only=True)

      class Meta:
          model = ImagingStudy
          fields = ['id', 'patient', 'patient_name', 'patient_mrn', 'study_date',
                    'modality', 'body_part', 'status', 'referring_physician',
                    'clinical_notes', 'images', 'diagnosis', 'created_at', 'updated_at']
          read_only_fields = ['created_at', 'updated_at']


class AuditLogSerializer(serializers.ModelSerializer):
      """
      Serializer for audit logs (read-only for compliance)
      """
      username = serializers.CharField(source='user.username', read_only=True)

      class Meta:
          model = AuditLog
          fields = ['id', 'user', 'username', 'action', 'resource_type', 'resource_id',
                    'ip_address', 'user_agent', 'timestamp', 'details']
          read_only_fields = '__all__'


class UserSerializer(serializers.ModelSerializer):
      """
      Serializer for User model (for radiologist assignments)
      """
      full_name = serializers.SerializerMethodField()

      class Meta:
          model = User
          fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name']

      def get_full_name(self, obj):
          return obj.get_full_name() or obj.username