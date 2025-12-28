"""
Celery tasks for asynchronous DICOM processing
Enhanced with:
- Idempotent locking
- Structured audit logging
- Correlation ID tracking for distributed tracing
"""
from celery import shared_task
from django.core.files.base import ContentFile
from django.core.files import File
from django.core.cache import cache
from django.db import transaction
import tempfile
import os
import logging
import uuid

from .models import ImagingStudy, DicomImage, TaskStatus, Patient, PatientReport, AuditLog
from .dicom_service import DicomParsingService
from .pdf_service import PatientReportGenerator
from django.core.files.storage import default_storage
from firstproject.correlation_middleware import set_correlation_id, get_correlation_id

logger = logging.getLogger(__name__)

# Lock timeout: 10 minutes (600 seconds)
LOCK_TIMEOUT = 600

# Processing pipeline version (update when DICOM parsing logic changes)
DICOM_PROCESSING_VERSION = "v1.2.0"


@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,  # Max 10 minutes between retries
    retry_jitter=True  # Add randomness to prevent thundering herd
)
def process_dicom_images_async(self, study_id, file_data_list, user_id=None, correlation_id=None):
    """
    Process multiple DICOM images asynchronously with idempotent locking

    PRODUCTION IMPROVEMENTS:
    - Redis distributed locking to prevent duplicate processing
    - Database pessimistic locking with select_for_update()
    - Explicit failure states before retry
    - Exponential backoff with jitter
    - Structured audit logging for system events
    - Correlation ID tracking for distributed tracing

    Args:
        study_id: ID of the imaging study
        file_data_list: List of dicts with 'filename', 'content', 'instance_number'
        user_id: ID of the user who initiated the task
        correlation_id: Correlation ID from the originating request (for tracing)

    Returns:
        dict: Results with created_images, skipped_images, errors
    """
    task_id = self.request.id
    lock_key = f"dicom-processing-{study_id}"

    # Set correlation ID for this task context (enables tracing across services)
    if not correlation_id:
        correlation_id = str(uuid.uuid4())
    set_correlation_id(correlation_id)

    logger.info(
        f"Starting DICOM processing for study {study_id}",
        extra={'correlation_id': correlation_id, 'task_id': task_id}
    )

    # IMPROVEMENT 1: Distributed lock (Redis) - Prevents duplicate processing across workers
    if not cache.add(lock_key, task_id, LOCK_TIMEOUT):
        existing_lock = cache.get(lock_key)
        logger.warning(
            f"Study {study_id} already being processed by task {existing_lock}. Skipping."
        )
        return {
            'status': 'skipped',
            'reason': 'already_processing',
            'existing_task_id': existing_lock
        }

    try:
        # Create or update task status
        task_status, created = TaskStatus.objects.get_or_create(
            task_id=task_id,
            defaults={
                'task_name': 'DICOM Image Processing',
                'status': 'processing',
                'total_items': len(file_data_list),
                'study_id': study_id,
                'user_id': user_id,
            }
        )

        if not created:
            task_status.status = 'processing'
            task_status.total_items = len(file_data_list)
            task_status.save()

        # IMPROVEMENT 2: Database-level pessimistic locking with select_for_update()
        try:
            with transaction.atomic():
                study = ImagingStudy.objects.select_for_update().get(id=study_id)

                # Check if already completed (idempotency)
                if study.status == 'completed':
                    logger.info(f"Study {study_id} already completed. Skipping.")
                    return {
                        'status': 'already_completed',
                        'study_id': study_id
                    }

                # Mark as in progress
                study.status = 'in_progress'
                study.error_message = ''  # Clear previous errors
                study.save()

                # IMPROVEMENT 3: Structured audit logging for system events
                AuditLog.objects.create(
                    actor_type='system',
                    action='process',
                    resource_type='ImagingStudy',
                    resource_id=study_id,
                    tenant_id=study.patient.hospital_id,
                    details={
                        'task_id': task_id,
                        'correlation_id': correlation_id,  # For distributed tracing
                        'total_files': len(file_data_list),
                        'initiated_by_user_id': user_id,
                    }
                )

        except ImagingStudy.DoesNotExist:
            # IMPROVEMENT 4: Explicit failure state
            task_status.status = 'failed'
            task_status.error_message = f'Study with ID {study_id} not found'
            task_status.save()

            # Create audit log for failure
            AuditLog.objects.create(
                actor_type='system',
                action='failed',
                resource_type='ImagingStudy',
                resource_id=study_id,
                details={
                    'task_id': task_id,
                    'error': 'Study not found',
                }
            )
            return {'error': 'Study not found'}

        created_images = []
        skipped_images = []
        errors = []

        for idx, file_data in enumerate(file_data_list):
            try:
                # Update progress
                task_status.processed_items = idx
                task_status.save()

                filename = file_data['filename']
                content = file_data['content']
                instance_number = file_data['instance_number']

                # Create a temporary file from the content
                with tempfile.NamedTemporaryFile(delete=False, suffix='.dcm') as temp_file:
                    temp_file.write(content)
                    temp_path = temp_file.name

                try:
                    # Check if it's a DICOM file
                    with open(temp_path, 'rb') as f:
                        file_obj = File(f, name=filename)
                        is_dicom = DicomParsingService.is_dicom_file(file_obj)

                    image_data = {
                        'study': study,
                        'instance_number': instance_number,
                        'is_dicom': is_dicom,
                    }

                    if is_dicom:
                        # Parse DICOM metadata
                        with open(temp_path, 'rb') as f:
                            file_obj = File(f, name=filename)
                            dicom_dataset, metadata = DicomParsingService.parse_dicom_file(file_obj)

                        if dicom_dataset and metadata:
                            # Check for duplicate SOP Instance UID
                            sop_uid = str(dicom_dataset.get('SOPInstanceUID', ''))
                            if sop_uid:
                                existing_image = DicomImage.objects.filter(sop_instance_uid=sop_uid).first()
                                if existing_image:
                                    skipped_images.append({
                                        'filename': filename,
                                        'reason': 'Duplicate SOP Instance UID',
                                        'sop_instance_uid': sop_uid
                                    })
                                    logger.info(f"Skipping duplicate DICOM: {filename} (SOP UID: {sop_uid})")
                                    continue

                            # Extract DICOM metadata
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

                            # Convert DICOM to PIL Image and save as JPEG
                            pil_image = DicomParsingService.dicom_to_pil_image(dicom_dataset)

                            if pil_image:
                                # Save as JPEG in temp file
                                jpeg_temp_path = temp_path + '.jpg'
                                pil_image.save(jpeg_temp_path, 'JPEG', quality=90)

                                # Read back and create DicomImage
                                with open(jpeg_temp_path, 'rb') as f:
                                    image = DicomImage.objects.create(
                                        **image_data,
                                        image_file=File(f, name=f"{filename}.jpg")
                                    )
                                    created_images.append({
                                        'id': image.id,
                                        'filename': filename,
                                        'instance_number': image.instance_number,
                                    })
                                    logger.info(f"Created DICOM image: {filename}")

                                # Clean up JPEG temp file
                                os.unlink(jpeg_temp_path)
                                continue

                    # Regular image processing (non-DICOM or DICOM parse failed)
                    with open(temp_path, 'rb') as f:
                        image = DicomImage.objects.create(
                            **image_data,
                            image_file=File(f, name=filename)
                        )
                        created_images.append({
                            'id': image.id,
                            'filename': filename,
                            'instance_number': image.instance_number,
                        })
                        logger.info(f"Created regular image: {filename}")

                finally:
                    # Clean up temp file
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)

            except Exception as e:
                error_msg = f"Error processing {file_data.get('filename', 'unknown')}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)
                task_status.failed_items += 1
                task_status.save()

        # Update final task status and study status
        task_status.processed_items = len(file_data_list)

        if errors:
            # IMPROVEMENT 4: Mark as failed BEFORE retry
            study.status = 'failed'
            study.error_message = '\n'.join(errors[:3])  # Store first 3 errors
            study.save()

            task_status.status = 'failed'
            task_status.error_message = '\n'.join(errors[:5])

            # Create audit log for failure
            AuditLog.objects.create(
                actor_type='system',
                action='failed',
                resource_type='ImagingStudy',
                resource_id=study_id,
                tenant_id=study.patient.hospital_id,
                details={
                    'task_id': task_id,
                    'total_errors': len(errors),
                    'error_messages': errors[:5],
                }
            )
        else:
            study.status = 'completed'
            study.processing_version = DICOM_PROCESSING_VERSION  # Record processing version
            study.save()
            task_status.status = 'completed'

            # Create audit log for successful completion
            AuditLog.objects.create(
                actor_type='system',
                action='update',
                resource_type='ImagingStudy',
                resource_id=study_id,
                tenant_id=study.patient.hospital_id,
                details={
                    'task_id': task_id,
                    'images_created': len(created_images),
                    'images_skipped': len(skipped_images),
                }
            )

        task_status.result = {
            'created': len(created_images),
            'skipped': len(skipped_images),
            'errors': len(errors),
            'created_images': created_images,
            'skipped_images': skipped_images,
            'error_messages': errors[:10],  # Limit error messages
        }
        task_status.save()

        return {
            'created_images': created_images,
            'skipped_images': skipped_images,
            'errors': errors,
            'task_id': task_id,
        }

    except Exception as exc:
        # IMPROVEMENT 4: Explicit failure state before retry
        try:
            ImagingStudy.objects.filter(id=study_id).update(
                status='failed',
                error_message=str(exc)[:500]
            )
            if 'task_status' in locals():
                task_status.status = 'failed'
                task_status.error_message = str(exc)
                task_status.save()
        except Exception as e:
            logger.error(f"Error updating failure state: {e}")

        # Retry with exponential backoff
        raise self.retry(exc=exc)

    finally:
        # ALWAYS release the distributed lock
        cache.delete(lock_key)
        logger.info(f"Released lock for study {study_id}")


@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def generate_patient_report_async(self, patient_id, user_id=None):
    """
    Generate PDF report for a patient asynchronously
    Enhanced with idempotent locking and audit logging

    Args:
        patient_id: ID of the patient
        user_id: ID of the user who requested the report

    Returns:
        dict: Results with pdf_url and filename
    """
    task_id = self.request.id
    lock_key = f"pdf-generation-{patient_id}"

    # Distributed lock to prevent duplicate PDF generation
    if not cache.add(lock_key, task_id, LOCK_TIMEOUT):
        existing_lock = cache.get(lock_key)
        logger.warning(
            f"PDF for patient {patient_id} already being generated by task {existing_lock}. Skipping."
        )
        return {
            'status': 'skipped',
            'reason': 'already_processing',
            'existing_task_id': existing_lock
        }

    try:
        # Create task status
        task_status, created = TaskStatus.objects.get_or_create(
            task_id=task_id,
            defaults={
                'task_name': 'PDF Report Generation',
                'status': 'processing',
                'total_items': 1,
                'user_id': user_id,
            }
        )

        if not created:
            task_status.status = 'processing'
            task_status.save()

        try:
            # Get patient with hospital relationship
            patient = Patient.objects.select_related('hospital').get(id=patient_id)
            logger.info(f"Generating PDF report for patient {patient.medical_record_number}")

            # Create audit log
            AuditLog.objects.create(
                actor_type='system',
                action='process',
                resource_type='Patient',
                resource_id=patient_id,
                tenant_id=patient.hospital_id,
                details={
                    'task_id': task_id,
                    'action': 'generate_pdf_report',
                    'initiated_by_user_id': user_id,
                }
            )

            # Update progress
            task_status.processed_items = 0
            task_status.save()

            # Generate PDF
            generator = PatientReportGenerator(patient)
            pdf_bytes = generator.generate()

            logger.info(f"PDF generated successfully, size: {len(pdf_bytes)} bytes")

            # Save PDF to storage with timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M')
            display_filename = f"{patient.medical_record_number}_{timestamp}.pdf"
            storage_path = f"patient_reports/{display_filename}"

            pdf_file = ContentFile(pdf_bytes)
            saved_path = default_storage.save(storage_path, pdf_file)

            # Get URL
            pdf_url = default_storage.url(saved_path)

            logger.info(f"PDF saved to: {saved_path}")

            # Get studies count
            studies_count = patient.imaging_studies.count()

            # Create PatientReport record
            report = PatientReport.objects.create(
                patient=patient,
                generated_by_id=user_id,
                pdf_file=saved_path,
                file_size=len(pdf_bytes),
                filename=display_filename,
                studies_count=studies_count,
                task_id=task_id,
            )

            logger.info(f"PatientReport record created: ID {report.id}")

            # Update task status
            task_status.processed_items = 1
            task_status.status = 'completed'
            task_status.result = {
                'pdf_url': pdf_url,
                'filename': display_filename,
                'file_size': len(pdf_bytes),
                'report_id': report.id,
            }
            task_status.save()

            # Create audit log for success
            AuditLog.objects.create(
                actor_type='system',
                action='create',
                resource_type='PatientReport',
                resource_id=report.id,
                tenant_id=patient.hospital_id,
                details={
                    'task_id': task_id,
                    'patient_id': patient_id,
                    'file_size': len(pdf_bytes),
                }
            )

            return {
                'pdf_url': pdf_url,
                'filename': display_filename,
                'report_id': report.id,
                'task_id': task_id,
            }

        except Patient.DoesNotExist:
            logger.error(f"Patient {patient_id} not found")
            task_status.status = 'failed'
            task_status.error_message = f'Patient with ID {patient_id} not found'
            task_status.failed_items = 1
            task_status.save()

            AuditLog.objects.create(
                actor_type='system',
                action='failed',
                resource_type='Patient',
                resource_id=patient_id,
                details={
                    'task_id': task_id,
                    'error': 'Patient not found',
                }
            )
            raise

    except Exception as exc:
        # Explicit failure state
        if 'task_status' in locals():
            task_status.status = 'failed'
            task_status.error_message = str(exc)
            task_status.failed_items = 1
            task_status.save()

        logger.error(f"PDF generation failed: {str(exc)}", exc_info=True)
        raise self.retry(exc=exc)

    finally:
        # Always release lock
        cache.delete(lock_key)
        logger.info(f"Released lock for patient PDF {patient_id}")


@shared_task
def purge_expired_studies():
    """
    Purge imaging studies that have exceeded their retention period.

    HIPAA Compliance:
    - Medical records must be retained for 6 years from last activity
    - After retention period, data should be securely deleted
    - All deletions must be audited

    This task should run nightly via Celery Beat.

    Returns:
        dict: Summary of purged studies
    """
    from django.utils import timezone

    today = timezone.now().date()

    # Find expired studies
    expired_studies = ImagingStudy.objects.filter(
        status='archived',  # Only purge archived studies
        retention_until__lt=today  # Retention date has passed
    ).select_related('patient', 'patient__hospital')

    purge_summary = {
        'total_purged': 0,
        'by_hospital': {},
        'errors': []
    }

    for study in expired_studies:
        try:
            hospital_name = study.patient.hospital.name
            study_id = study.id

            # Create audit log BEFORE deletion (can't after - record is gone!)
            AuditLog.objects.create(
                actor_type='system',
                action='delete',
                resource_type='ImagingStudy',
                resource_id=study_id,
                tenant_id=study.patient.hospital_id,
                details={
                    'reason': 'retention_period_expired',
                    'retention_until': str(study.retention_until),
                    'study_date': str(study.study_date),
                    'patient_mrn': study.patient.medical_record_number,
                    'modality': study.modality,
                    'images_count': study.images.count(),
                }
            )

            # Delete study (cascades to DicomImages)
            study.delete()

            # Update summary
            purge_summary['total_purged'] += 1
            purge_summary['by_hospital'][hospital_name] = purge_summary['by_hospital'].get(hospital_name, 0) + 1

            logger.info(
                f"Purged expired study {study_id} (retention_until: {study.retention_until})"
            )

        except Exception as e:
            error_msg = f"Failed to purge study {study.id}: {str(e)}"
            purge_summary['errors'].append(error_msg)
            logger.error(error_msg, exc_info=True)

    # Log summary
    if purge_summary['total_purged'] > 0:
        logger.info(
            f"Data retention purge completed: {purge_summary['total_purged']} studies purged"
        )
    else:
        logger.info("Data retention purge completed: No expired studies found")

    return purge_summary


@shared_task
def calculate_retention_dates():
    """
    Calculate and set retention dates for studies that don't have one.

    HIPAA: 6 years from last activity (study date or last update)

    This task can run weekly to catch any studies missing retention dates.

    Returns:
        dict: Summary of updated studies
    """
    from django.utils import timezone
    from datetime import timedelta

    # HIPAA retention period: 6 years
    RETENTION_YEARS = 6

    # Find studies without retention date
    studies_without_retention = ImagingStudy.objects.filter(
        retention_until__isnull=True
    )

    updated_count = 0

    for study in studies_without_retention:
        # Calculate retention date: 6 years from study date
        retention_date = (study.study_date.date() + timedelta(days=365 * RETENTION_YEARS))

        study.retention_until = retention_date
        study.save(update_fields=['retention_until'])

        updated_count += 1

    logger.info(f"Updated retention dates for {updated_count} studies")

    return {
        'updated_count': updated_count,
        'retention_years': RETENTION_YEARS
    }
