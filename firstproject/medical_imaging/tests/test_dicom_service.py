import pytest
from io import BytesIO
from PIL import Image as PILImage
from medical_imaging.dicom_service import DicomParsingService


@pytest.mark.unit
class TestDicomParsingService:
    """Test DICOM parsing service functionality"""

    def test_is_dicom_file_with_non_dicom(self):
        """Test detecting non-DICOM file"""
        # Create a simple JPEG image
        img = PILImage.new('RGB', (100, 100), color='red')
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        img_bytes.name = 'test.jpg'

        result = DicomParsingService.is_dicom_file(img_bytes)
        assert result is False

    def test_is_dicom_file_with_invalid_data(self):
        """Test detecting invalid file data"""
        invalid_bytes = BytesIO(b'invalid data')
        invalid_bytes.name = 'test.dcm'

        result = DicomParsingService.is_dicom_file(invalid_bytes)
        assert result is False

    def test_parse_dicom_file_with_non_dicom(self):
        """Test parsing non-DICOM file returns None"""
        img = PILImage.new('RGB', (100, 100), color='blue')
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        img_bytes.name = 'test.jpg'

        dataset, metadata = DicomParsingService.parse_dicom_file(img_bytes)
        assert dataset is None
        assert metadata is None

    def test_extract_metadata_structure(self):
        """Test metadata extraction returns correct structure"""
        # This test would require a real DICOM file
        # For now, we test that the method exists and has correct signature
        assert hasattr(DicomParsingService, 'extract_metadata')
        assert callable(DicomParsingService.extract_metadata)

    def test_dicom_to_pil_image_with_none(self):
        """Test converting None DICOM dataset returns None"""
        result = DicomParsingService.dicom_to_pil_image(None)
        assert result is None

    def test_apply_windowing_basic(self):
        """Test basic windowing function"""
        import numpy as np

        # Create test pixel array
        pixel_array = np.array([[0, 100, 200], [300, 400, 500]], dtype=np.float32)
        window_center = 250
        window_width = 200

        result = DicomParsingService._apply_windowing(
            pixel_array, window_center, window_width
        )

        # Result should be normalized to 0-255
        assert result.min() >= 0
        assert result.max() <= 255
        assert result.dtype == np.uint8

    def test_apply_windowing_with_rescale(self):
        """Test windowing with rescale parameters"""
        import numpy as np

        pixel_array = np.array([[0, 100, 200]], dtype=np.float32)
        window_center = 40
        window_width = 400
        rescale_intercept = -1024
        rescale_slope = 1

        result = DicomParsingService._apply_windowing(
            pixel_array, window_center, window_width,
            rescale_intercept, rescale_slope
        )

        assert result is not None
        assert result.shape == pixel_array.shape

    def test_normalize_to_uint8(self):
        """Test normalization to uint8"""
        import numpy as np

        # Create test array with various values
        test_array = np.array([[-100, 0, 100, 200, 300]], dtype=np.float32)

        result = DicomParsingService._normalize_to_uint8(test_array)

        assert result.dtype == np.uint8
        assert result.min() >= 0
        assert result.max() <= 255

    def test_normalize_to_uint8_single_value(self):
        """Test normalization when all values are the same"""
        import numpy as np

        test_array = np.array([[100, 100, 100]], dtype=np.float32)

        result = DicomParsingService._normalize_to_uint8(test_array)

        # Should handle single-value case without division by zero
        assert result.dtype == np.uint8
        assert len(result.shape) == 2


@pytest.mark.unit
class TestDicomServiceHelpers:
    """Test DICOM service helper methods"""

    def test_service_has_required_methods(self):
        """Test that service has all required methods"""
        required_methods = [
            'is_dicom_file',
            'parse_dicom_file',
            'extract_metadata',
            'dicom_to_pil_image',
            '_apply_windowing',
            '_normalize_to_uint8'
        ]

        for method in required_methods:
            assert hasattr(DicomParsingService, method)
            assert callable(getattr(DicomParsingService, method))

    def test_extract_metadata_handles_empty_dataset(self):
        """Test metadata extraction with missing fields"""
        # Create a minimal mock dataset
        class MockDataset:
            def get(self, key, default=None):
                return default

        mock_ds = MockDataset()
        metadata = DicomParsingService.extract_metadata(mock_ds)

        # Should return dict with expected structure
        assert isinstance(metadata, dict)
        assert 'patient' in metadata
        assert 'spatial' in metadata
        assert 'image' in metadata
        assert 'display' in metadata
        assert 'equipment' in metadata
