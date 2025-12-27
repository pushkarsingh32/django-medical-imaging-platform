"""
Celery tasks for asynchronous DICOM processing
"""
from celery import shared_task
from django.core.files.base import ContentFile
from django.core.files import File
import tempfile
import os
import logging

from .models import ImagingStudy, DicomImage, TaskStatus
from .dicom_service import DicomParsingService

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
