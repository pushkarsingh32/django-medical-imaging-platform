from django.contrib import admin
from .models import Hospital, Patient, ImagingStudy, DicomImage, Diagnosis, AuditLog
# Register your models here.

@admin.register(Hospital)
class HospitalAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact_email', 'contact_phone', 'created_at']
    search_fields= ['name', 'contact_email']
    list_filter = ['created_at']

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display= ['medical_record_number', 'full_name', 'gender', 'date_of_birth', 'hospital']
    search_fields = ['medical_record_number', 'first_name','last_name', 'email']
    list_filter = ['hospital', 'gender', 'created_at']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Personal Information',{
            'fields': ('first_name', 'last_name', 'date_of_birth', 'gender')
        }),
        ('Contact Information', {
            'fields': ('phone', 'email', 'address')
        }),
        ('Hospital Details',
         {
             'fields': ('hospital', 'medical_record_number')
         }),
         (
             'Metadata', {
                 'fields': ('created_at', 'updated_at'),
                 'classes': ('collapse',)
             }
         ),
    )

@admin.register(ImagingStudy)
class ImagingStudyAdmin(admin.ModelAdmin):
      list_display = ['id', 'patient', 'modality', 'body_part', 'study_date', 'status']
      search_fields = ['patient__first_name', 'patient__last_name',
  'patient__medical_record_number', 'body_part']
      list_filter = ['modality', 'status', 'study_date']
      readonly_fields = ['created_at', 'updated_at']
      date_hierarchy = 'study_date'

      fieldsets = (
          ('Patient Information', {
              'fields': ('patient',)
          }),
          ('Study Details', {
              'fields': ('study_date', 'modality', 'body_part', 'status')
          }),
          ('Clinical Information', {
              'fields': ('referring_physician', 'clinical_notes')
          }),
          ('Metadata', {
              'fields': ('created_at', 'updated_at'),
              'classes': ('collapse',)
          }),
      )


@admin.register(DicomImage)
class DicomImageAdmin(admin.ModelAdmin):
      list_display = ['id', 'study', 'instance_number', 'file_size_bytes', 'uploaded_at']
      search_fields = ['study__patient__first_name', 'study__patient__last_name']
      list_filter = ['uploaded_at']
      readonly_fields = ['uploaded_at', 'file_size_bytes']


@admin.register(Diagnosis)
class DiagnosisAdmin(admin.ModelAdmin):
      list_display = ['id', 'study', 'radiologist', 'severity', 'diagnosed_at']
      search_fields = ['study__patient__first_name', 'study__patient__last_name', 'findings',
  'impression']
      list_filter = ['severity', 'diagnosed_at']
      readonly_fields = ['diagnosed_at', 'updated_at']

      fieldsets = (
          ('Study Information', {
              'fields': ('study', 'radiologist')
          }),
          ('Diagnosis', {
              'fields': ('findings', 'impression', 'severity', 'recommendations')
          }),
          ('Metadata', {
              'fields': ('diagnosed_at', 'updated_at'),
              'classes': ('collapse',)
          }),
      )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
      list_display = ['id', 'user', 'action', 'resource_type', 'resource_id', 'ip_address',
  'timestamp']
      search_fields = ['user__username', 'resource_type', 'ip_address']
      list_filter = ['action', 'resource_type', 'timestamp']
      readonly_fields = ['user', 'action', 'resource_type', 'resource_id', 'ip_address',
  'user_agent', 'timestamp', 'details']

      def has_add_permission(self, request):
          # Audit logs should only be created by system, not manually
          return False

      def has_change_permission(self, request, obj=None):
          # Audit logs should never be modified
          return False