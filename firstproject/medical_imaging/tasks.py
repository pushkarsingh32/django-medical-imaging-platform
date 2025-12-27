"""
Celery tasks for asynchronous DICOM processing
"""
from celery import shared_task
from django.core.files.base import ContentFile
from django.core.files import File
import tempfile
import os
import logging

from .models import ImagingStudy, DicomImage, TaskStatus, Patient, PatientReport
from .dicom_service import DicomParsingService
from .pdf_service import PatientReportGenerator
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_dicom_images_async(self, study_id, file_data_list, user_id=None):
    """
    Process multiple DICOM images asynchronously

    Args:
        study_id: ID of the imaging study
        file_data_list: List of dicts with 'filename', 'content', 'instance_number'
        user_id: ID of the user who initiated the task

    Returns:
        dict: Results with created_images, skipped_images, errors
    """
    task_id = self.request.id

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

    try:
        study = ImagingStudy.objects.get(id=study_id)
    except ImagingStudy.DoesNotExist:
        task_status.status = 'failed'
        task_status.error_message = f'Study with ID {study_id} not found'
        task_status.save()
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

    # Update final task status
    task_status.processed_items = len(file_data_list)
    task_status.status = 'completed' if not errors else 'failed'
    task_status.result = {
        'created': len(created_images),
        'skipped': len(skipped_images),
        'errors': len(errors),
        'created_images': created_images,
        'skipped_images': skipped_images,
        'error_messages': errors[:10],  # Limit error messages
    }
    if errors:
        task_status.error_message = '\n'.join(errors[:5])  # Store first 5 errors
    task_status.save()

    return {
        'created_images': created_images,
        'skipped_images': skipped_images,
        'errors': errors,
        'task_id': task_id,
    }


@shared_task(bind=True, max_retries=3)
def generate_patient_report_async(self, patient_id, user_id=None):
    """
    Generate PDF report for a patient asynchronously

    Args:
        patient_id: ID of the patient
        user_id: ID of the user who requested the report

    Returns:
        dict: Results with pdf_url and filename
    """
    task_id = self.request.id

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
        # Get patient
        patient = Patient.objects.get(id=patient_id)
        logger.info(f"Generating PDF report for patient {patient.medical_record_number}")

        # Update progress
        task_status.processed_items = 0
        task_status.save()

        # Generate PDF
        generator = PatientReportGenerator(patient)
        pdf_bytes = generator.generate()

        logger.info(f"PDF generated successfully, size: {len(pdf_bytes)} bytes")

        # Save PDF to storage
        filename = f"patient_reports/patient_{patient.medical_record_number}_{task_id[:8]}.pdf"
        pdf_file = ContentFile(pdf_bytes)
        saved_path = default_storage.save(filename, pdf_file)

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
            filename=f"patient_{patient.medical_record_number}_report.pdf",
            studies_count=studies_count,
            task_id=task_id,
        )

        logger.info(f"PatientReport record created: ID {report.id}")

        # Update task status
        task_status.processed_items = 1
        task_status.status = 'completed'
        task_status.result = {
            'pdf_url': pdf_url,
            'filename': f"patient_{patient.medical_record_number}_report.pdf",
            'file_size': len(pdf_bytes),
            'report_id': report.id,
        }
        task_status.save()

        return {
            'pdf_url': pdf_url,
            'filename': f"patient_{patient.medical_record_number}_report.pdf",
            'report_id': report.id,
            'task_id': task_id,
        }

    except Patient.DoesNotExist:
        logger.error(f"Patient {patient_id} not found")
        task_status.status = 'failed'
        task_status.error_message = f'Patient with ID {patient_id} not found'
        task_status.failed_items = 1
        task_status.save()
        raise

    except Exception as e:
        logger.error(f"PDF generation failed: {str(e)}", exc_info=True)
        task_status.status = 'failed'
        task_status.error_message = str(e)
        task_status.failed_items = 1
        task_status.save()
        raise
