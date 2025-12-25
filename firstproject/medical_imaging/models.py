from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator 

# Create your models here.

class Hospital(models.Model):
    """
    Respresents a hospital/clinin organization.
    Multi Tenancy: Each Hospital has isolated data 
    """
    name = models.CharField(max_length=200, unique=True)
    address = models.TextField()
    contact_email=  models.EmailField()
    contact_phone = models.CharField(max_length=20)
    created_at= models.DateTimeField(auto_now_add=True)

    class Meta: 
        ordering= ['name']

    def __str__(self):
        return self.name
    

class Patient(models.Model):
    """
    Patient Records - linked to a hospital 
    """
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other')
    ]

    hospital = models.ForeignKey(
        Hospital, 
        on_delete=models.PROTECT,  # can't delete hospital if patients exist 
        related_name='patients'
    )

    medical_record_number = models.CharField(max_length=50, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    phone = models.CharField(max_length=20, blank=True)
    email= models.EmailField(blank=True)
    address = models.CharField(max_length=500, blank=True)
    created_at= models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta: 
        ordering = ['last_name', 'first_name']
        indexes = [
            models.Index(fields=['medical_record_number']),
            models.Index(fields= ['hospital', 'last_name']),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} (MRN: {self.medical_record_number})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    

class ImagingStudy(models.Model):
    """
    A single imaging session (e.g., one CT scan appointment)
    can contain multiple images
    """
    MODALITY_CHOICES = [
        ("CT", 'CT SCAN'),
        ('MRI', "MRI"),
        ('XRAY', 'X-Ray'),
        ('ULTRASOUND', 'Ultrasound'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('archived', 'Archieved'),
    ]

    patient = models.ForeignKey(
        Patient, 
        on_delete=models.CASCADE,# Delete studies if patient deleted,
        related_name='imaging_studies',
    )
    study_date = models.DateTimeField()
    modality=models.CharField(max_length=20, choices=MODALITY_CHOICES)
    body_part = models.CharField(max_length=100, help_text="e.g. Chest, Lung, Brain")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    referring_physician = models.CharField(max_length=200, blank=True)
    clinical_notes = models.TextField(blank=True, help_text='Reason for study')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta: 
        ordering = ['-study_date']
        verbose_name_plural = 'Imaging Studies'
        indexes=[
            models.Index(fields=['patient', '-study_date']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.patient.full_name} -  {self.modality} ({self.study_date.date()})"
    

class DicomImage(models.Model):
    """
    Individual image file within a study
    In real system: would parse DICOM metadate
    """

    study = models.ForeignKey(
        ImagingStudy, 
        on_delete=models.CASCADE,
        related_name='images'
    )

    image_file = models.FileField(upload_to='dicom_image/%Y/%m/%d/')
    instance_number = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text='Image sequence numer in study'
    )

    # Simulated DICOM Metadata
    slice_thickness = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        null=True, 
        blank=True, 
        help_text='in mm'
    )

    pixel_spacing = models.CharField(max_length=50, blank=True)
    file_size_bytes = models.BigIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta: 
        ordering =  ['instance_number']
        unique_together = ['study', 'instance_number']

    def __str__(self):
        return f"{self.study} - Image {self.instance_number}"
    

class Diagnosis(models.Model):
      """
      Radiologist's findings and diagnosis for a study
      """
      SEVERITY_CHOICES = [
          ('normal', 'Normal'),
          ('minor', 'Minor Finding'),
          ('moderate', 'Moderate Concern'),
          ('severe', 'Severe - Urgent'),
      ]

      study = models.OneToOneField(
          ImagingStudy,
          on_delete=models.CASCADE,
          related_name='diagnosis'
      )
      radiologist = models.ForeignKey(
          User,
          on_delete=models.SET_NULL,
          null=True,
          related_name='diagnoses'
      )
      findings = models.TextField(help_text="Detailed radiologist findings")
      impression = models.TextField(help_text="Summary/conclusion")
      severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='normal')
      recommendations = models.TextField(blank=True)
      diagnosed_at = models.DateTimeField(auto_now_add=True)
      updated_at = models.DateTimeField(auto_now=True)

      class Meta:
          ordering = ['-diagnosed_at']
          verbose_name_plural = 'Diagnoses'

      def __str__(self):
          return f"Diagnosis for {self.study}"


class AuditLog(models.Model):
      """
      HIPAA compliance: Track all data access and modifications
      """
      ACTION_CHOICES = [
          ('view', 'Viewed'),
          ('create', 'Created'),
          ('update', 'Updated'),
          ('delete', 'Deleted'),
          ('download', 'Downloaded'),
      ]

      user = models.ForeignKey(
          User,
          on_delete=models.SET_NULL,
          null=True,
          related_name='audit_logs'
      )
      action = models.CharField(max_length=20, choices=ACTION_CHOICES)
      resource_type = models.CharField(max_length=50, help_text="e.g., Patient, ImagingStudy")
      resource_id = models.IntegerField(help_text="ID of the affected record")
      ip_address = models.GenericIPAddressField()
      user_agent = models.TextField(blank=True)
      timestamp = models.DateTimeField(auto_now_add=True)
      details = models.JSONField(default=dict, blank=True)

      class Meta:
          ordering = ['-timestamp']
          indexes = [
              models.Index(fields=['-timestamp']),
              models.Index(fields=['user', '-timestamp']),
              models.Index(fields=['resource_type', 'resource_id']),
          ]

      def __str__(self):
          return f"{self.user} {self.action} {self.resource_type}#{self.resource_id}"