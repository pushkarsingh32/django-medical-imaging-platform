"""
DICOM File Processing Service
Handles parsing, metadata extraction, and image conversion for DICOM medical imaging files.

This demonstrates professional medical imaging capabilities:
- HL7 DICOM standard compliance
- Metadata extraction (patient info, study details, equipment data)
- Pixel data extraction and conversion
- Windowing/Leveling for CT/MRI scans
"""
import logging
import io
from typing import Dict, Optional, Tuple
from datetime import datetime
import pydicom
from pydicom.errors import InvalidDicomError
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class DicomParsingService:
    """Service for parsing DICOM files and extracting medical imaging data."""

    @staticmethod
    def is_dicom_file(file_path_or_bytes) -> bool:
        """
        Check if a file is a valid DICOM file.

        Args:
            file_path_or_bytes: File path (str) or file-like object

        Returns:
            bool: True if valid DICOM file
        """
        try:
            pydicom.dcmread(file_path_or_bytes, stop_before_pixels=True)
            return True
        except (InvalidDicomError, Exception):
            return False

    @staticmethod
    def extract_metadata(dicom_dataset: pydicom.Dataset) -> Dict:
        """
        Extract comprehensive metadata from DICOM dataset.

        DICOM Tags are standardized (HL7/NEMA standard)

        Args:
            dicom_dataset: Parsed DICOM dataset

        Returns:
            dict: Extracted metadata
        """
        metadata = {}

        # Patient Information (Group 0010)
        metadata['patient'] = {
            'name': str(dicom_dataset.get('PatientName', '')),
            'id': str(dicom_dataset.get('PatientID', '')),
            'birth_date': str(dicom_dataset.get('PatientBirthDate', '')),
            'sex': str(dicom_dataset.get('PatientSex', '')),
            'age': str(dicom_dataset.get('PatientAge', '')),
            'weight': str(dicom_dataset.get('PatientWeight', '')),
        }

        # Study Information (Group 0020, 0008)
        metadata['study'] = {
            'instance_uid': str(dicom_dataset.get('StudyInstanceUID', '')),
            'date': str(dicom_dataset.get('StudyDate', '')),
            'time': str(dicom_dataset.get('StudyTime', '')),
            'description': str(dicom_dataset.get('StudyDescription', '')),
            'id': str(dicom_dataset.get('StudyID', '')),
            'accession_number': str(dicom_dataset.get('AccessionNumber', '')),
        }

        # Series Information
        metadata['series'] = {
            'instance_uid': str(dicom_dataset.get('SeriesInstanceUID', '')),
            'number': str(dicom_dataset.get('SeriesNumber', '')),
            'description': str(dicom_dataset.get('SeriesDescription', '')),
            'modality': str(dicom_dataset.get('Modality', '')),
            'body_part': str(dicom_dataset.get('BodyPartExamined', '')),
        }

        # Image Information
        metadata['image'] = {
            'instance_number': int(dicom_dataset.get('InstanceNumber', 0)),
            'rows': int(dicom_dataset.get('Rows', 0)),
            'columns': int(dicom_dataset.get('Columns', 0)),
            'bits_allocated': int(dicom_dataset.get('BitsAllocated', 0)),
            'bits_stored': int(dicom_dataset.get('BitsStored', 0)),
            'samples_per_pixel': int(dicom_dataset.get('SamplesPerPixel', 1)),
        }

        # Spatial Information (Critical for 3D reconstruction)
        metadata['spatial'] = {
            'slice_thickness': float(dicom_dataset.get('SliceThickness', 0)) if dicom_dataset.get('SliceThickness') else None,
            'pixel_spacing': str(dicom_dataset.get('PixelSpacing', '')),
            'slice_location': float(dicom_dataset.get('SliceLocation', 0)) if dicom_dataset.get('SliceLocation') else None,
            'image_position': str(dicom_dataset.get('ImagePositionPatient', '')),
            'image_orientation': str(dicom_dataset.get('ImageOrientationPatient', '')),
        }

        # Equipment Information
        metadata['equipment'] = {
            'manufacturer': str(dicom_dataset.get('Manufacturer', '')),
            'model': str(dicom_dataset.get('ManufacturerModelName', '')),
            'station_name': str(dicom_dataset.get('StationName', '')),
            'software_version': str(dicom_dataset.get('SoftwareVersions', '')),
        }

        # Window/Level (for CT/MRI display)
        metadata['display'] = {
            'window_center': str(dicom_dataset.get('WindowCenter', '')),
            'window_width': str(dicom_dataset.get('WindowWidth', '')),
            'rescale_intercept': float(dicom_dataset.get('RescaleIntercept', 0)),
            'rescale_slope': float(dicom_dataset.get('RescaleSlope', 1)),
        }

        return metadata

    @staticmethod
    def parse_dicom_file(file_path_or_bytes) -> Tuple[Optional[pydicom.Dataset], Optional[Dict]]:
        """
        Parse DICOM file and extract metadata.

        Args:
            file_path_or_bytes: File path or file-like object

        Returns:
            Tuple of (DICOM dataset, metadata dict) or (None, None) on error
        """
        try:
            # Read DICOM file
            dicom_dataset = pydicom.dcmread(file_path_or_bytes)

            # Extract metadata
            metadata = DicomParsingService.extract_metadata(dicom_dataset)

            logger.info(f"Successfully parsed DICOM file: {metadata['study']['instance_uid']}")
            return dicom_dataset, metadata

        except InvalidDicomError as e:
            logger.error(f"Invalid DICOM file: {str(e)}")
            return None, None
        except Exception as e:
            logger.error(f"Error parsing DICOM file: {str(e)}")
            return None, None

    @staticmethod
    def extract_pixel_array(dicom_dataset: pydicom.Dataset) -> Optional[np.ndarray]:
        """
        Extract pixel data from DICOM dataset.

        Args:
            dicom_dataset: Parsed DICOM dataset

        Returns:
            numpy.ndarray: Pixel data or None
        """
        try:
            # Get pixel array (this handles decompression if needed)
            pixels = dicom_dataset.pixel_array

            # Apply rescale slope and intercept (converts to Hounsfield units for CT)
            rescale_intercept = float(dicom_dataset.get('RescaleIntercept', 0))
            rescale_slope = float(dicom_dataset.get('RescaleSlope', 1))

            if rescale_slope != 1 or rescale_intercept != 0:
                pixels = pixels * rescale_slope + rescale_intercept

            return pixels

        except Exception as e:
            logger.error(f"Error extracting pixel array: {str(e)}")
            return None

    @staticmethod
    def apply_windowing(pixels: np.ndarray, window_center: float, window_width: float) -> np.ndarray:
        """
        Apply window/level to pixel data for optimal viewing.
        This is critical for CT scans (Hounsfield units).

        Args:
            pixels: Input pixel array
            window_center: Center of the intensity window
            window_width: Width of the intensity window

        Returns:
            numpy.ndarray: Windowed pixel data (0-255 range)
        """
        lower = window_center - window_width / 2
        upper = window_center + window_width / 2

        # Clip and normalize to 0-255
        windowed = np.clip(pixels, lower, upper)
        windowed = ((windowed - lower) / (upper - lower) * 255).astype(np.uint8)

        return windowed

    @staticmethod
    def dicom_to_pil_image(dicom_dataset: pydicom.Dataset, apply_window: bool = True) -> Optional[Image.Image]:
        """
        Convert DICOM to PIL Image for display/processing.

        Args:
            dicom_dataset: Parsed DICOM dataset
            apply_window: Whether to apply windowing (default True for CT/MRI)

        Returns:
            PIL.Image: Converted image or None
        """
        try:
            # Extract pixel data
            pixels = DicomParsingService.extract_pixel_array(dicom_dataset)

            if pixels is None:
                return None

            # Apply windowing if requested and available
            if apply_window:
                window_center = dicom_dataset.get('WindowCenter', None)
                window_width = dicom_dataset.get('WindowWidth', None)

                if window_center is not None and window_width is not None:
                    # Handle multiple window values (take first)
                    if isinstance(window_center, (list, pydicom.multival.MultiValue)):
                        window_center = float(window_center[0])
                    else:
                        window_center = float(window_center)

                    if isinstance(window_width, (list, pydicom.multival.MultiValue)):
                        window_width = float(window_width[0])
                    else:
                        window_width = float(window_width)

                    pixels = DicomParsingService.apply_windowing(pixels, window_center, window_width)
                else:
                    # No windowing info - normalize to 0-255
                    pixels = ((pixels - pixels.min()) / (pixels.max() - pixels.min()) * 255).astype(np.uint8)
            else:
                # Normalize without windowing
                pixels = ((pixels - pixels.min()) / (pixels.max() - pixels.min()) * 255).astype(np.uint8)

            # Handle photometric interpretation (grayscale vs RGB)
            photometric = str(dicom_dataset.get('PhotometricInterpretation', ''))

            if photometric == 'MONOCHROME1':
                # Invert grayscale (0=white in DICOM)
                pixels = 255 - pixels

            # Create PIL Image
            if len(pixels.shape) == 2:
                # Grayscale
                image = Image.fromarray(pixels, mode='L')
            else:
                # RGB
                image = Image.fromarray(pixels, mode='RGB')

            return image

        except Exception as e:
            logger.error(f"Error converting DICOM to PIL Image: {str(e)}")
            return None

    @staticmethod
    def get_formatted_date(dicom_date: str) -> Optional[str]:
        """
        Convert DICOM date format (YYYYMMDD) to readable format.

        Args:
            dicom_date: DICOM date string

        Returns:
            str: Formatted date or None
        """
        try:
            if not dicom_date or len(dicom_date) < 8:
                return None

            date_obj = datetime.strptime(dicom_date, '%Y%m%d')
            return date_obj.strftime('%Y-%m-%d')
        except Exception:
            return None

    @staticmethod
    def get_formatted_time(dicom_time: str) -> Optional[str]:
        """
        Convert DICOM time format (HHMMSS.FFFFFF) to readable format.

        Args:
            dicom_time: DICOM time string

        Returns:
            str: Formatted time or None
        """
        try:
            if not dicom_time:
                return None

            # Handle fractional seconds
            time_parts = dicom_time.split('.')
            base_time = time_parts[0]

            if len(base_time) >= 6:
                time_obj = datetime.strptime(base_time[:6], '%H%M%S')
                return time_obj.strftime('%H:%M:%S')

            return None
        except Exception:
            return None
