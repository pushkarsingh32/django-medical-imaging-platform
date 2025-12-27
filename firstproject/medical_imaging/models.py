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
        indexes = [
            models.Index(fields=['name']),  # Fast hospital lookup
            models.Index(fields=['created_at']),  # For recent hospitals query
        ]

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
            models.Index(fields=['medical_record_number']),  # Unique lookup
            models.Index(fields=['hospital', 'last_name']),  # Hospital patient list
            models.Index(fields=['hospital', 'created_at']),  # Recent patients per hospital
            models.Index(fields=['gender']),  # Gender filtering
            models.Index(fields=['date_of_birth']),  # Age-based queries
            models.Index(fields=['email']),  # Email lookup for patient portal
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
            models.Index(fields=['patient', '-study_date']),  # Patient study history
            models.Index(fields=['status']),  # Status filtering
            models.Index(fields=['modality', '-study_date']),  # Modality-based queries
            models.Index(fields=['status', '-study_date']),  # Pending studies, etc.
            models.Index(fields=['-study_date']),  # Recent studies
            models.Index(fields=['body_part']),  # Body part filtering
        ]

    def __str__(self):
        return f"{self.patient.full_name} -  {self.modality} ({self.study_date.date()})"
    

class DicomImage(models.Model):
    """
    Individual DICOM image file within a study.
    Stores actual DICOM metadata parsed from files using pydicom.
    """

    study = models.ForeignKey(
        ImagingStudy,
        on_delete=models.CASCADE,
        related_name='images'
    )

    image_file = models.FileField(upload_to='dicom_image/%Y/%m/%d/')
    instance_number = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text='Image sequence number in study'
    )

    # DICOM Metadata (Spatial Information)
    slice_thickness = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Slice thickness in mm'
    )
    pixel_spacing = models.CharField(max_length=50, blank=True, help_text='Pixel spacing (row, column)')
    slice_location = models.FloatField(
        null=True,
        blank=True,
        help_text='Slice location in mm'
    )

    # DICOM Image Properties
    rows = models.IntegerField(null=True, blank=True, help_text='Image height in pixels')
    columns = models.IntegerField(null=True, blank=True, help_text='Image width in pixels')
    bits_allocated = models.IntegerField(null=True, blank=True, help_text='Bits allocated per pixel')
    bits_stored = models.IntegerField(null=True, blank=True, help_text='Bits stored per pixel')

    # DICOM Display Parameters (Window/Level for CT/MRI)
    window_center = models.CharField(max_length=50, blank=True, help_text='Window center for display')
    window_width = models.CharField(max_length=50, blank=True, help_text='Window width for display')
    rescale_intercept = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Rescale intercept for Hounsfield units'
    )
    rescale_slope = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=1,
        help_text='Rescale slope for Hounsfield units'
    )

    # DICOM Equipment Info
    manufacturer = models.CharField(max_length=200, blank=True, help_text='Equipment manufacturer')
    manufacturer_model = models.CharField(max_length=200, blank=True, help_text='Equipment model')

    # DICOM Unique Identifiers
    sop_instance_uid = models.CharField(
        max_length=200,
        blank=True,
        unique=True,
        null=True,
        help_text='SOP Instance UID (unique DICOM identifier)'
    )

    # Full DICOM metadata (JSON storage for all tags)
    dicom_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text='Complete DICOM metadata as JSON'
    )

    # File information
    file_size_bytes = models.BigIntegerField(default=0)
    is_dicom = models.BooleanField(default=False, help_text='True if file is valid DICOM format')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering =  ['instance_number']
        unique_together = ['study', 'instance_number']
        indexes = [
            models.Index(fields=['study', 'instance_number']),  # Fast image lookup
            models.Index(fields=['-uploaded_at']),  # Recent uploads
            models.Index(fields=['file_size_bytes']),  # Size-based queries
        ]

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
          indexes = [
              models.Index(fields=['-diagnosed_at']),  # Recent diagnoses
              models.Index(fields=['severity', '-diagnosed_at']),  # Urgent cases
              models.Index(fields=['radiologist', '-diagnosed_at']),  # Radiologist workload
          ]

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


class ContactMessage(models.Model):
    """
    Contact form submissions from the website
    """
    STATUS_CHOICES = [
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]

    name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    subject = models.CharField(max_length=300)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, help_text="Internal notes for staff")

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Contact Message'
        verbose_name_plural = 'Website - Contact Messages'
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.name} - {self.subject} ({self.created_at.date()})"


class TaskStatus(models.Model):
    """
    Track status of asynchronous Celery tasks
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    task_id = models.CharField(max_length=255, unique=True, db_index=True)
    task_name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Task details
    total_items = models.IntegerField(default=0)
    processed_items = models.IntegerField(default=0)
    failed_items = models.IntegerField(default=0)

    # Result data
    result = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    # Relationships
    study = models.ForeignKey(
        'ImagingStudy',
        on_delete=models.CASCADE,
        related_name='tasks',
        null=True,
        blank=True
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Task Status'
        verbose_name_plural = 'Task Statuses'
        indexes = [
            models.Index(fields=['task_id']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['study', '-created_at']),
        ]

    def __str__(self):
        return f"{self.task_name} - {self.status}"

    @property
    def progress_percentage(self):
        """Calculate progress percentage"""
        if self.total_items == 0:
            return 0
        return int((self.processed_items / self.total_items) * 100)