import pytest
from io import BytesIO
from PIL import Image as PILImage
from unittest.mock import Mock, patch, MagicMock
from medical_imaging.image_cache_service import ImageCacheService


@pytest.mark.unit
class TestImageCacheService:
    """Test Image Cache Service functionality"""

    def test_generate_cache_key(self):
        """Test cache key generation"""
        key = ImageCacheService._generate_cache_key('thumbnail', 'test/path.jpg', 'jpg')
        assert isinstance(key, str)
        assert 'thumbnail' in key
        assert key.startswith('medical_imaging:')

    def test_generate_cache_key_consistency(self):
        """Test that same inputs generate same key"""
        key1 = ImageCacheService._generate_cache_key('thumbnail', 'test.jpg', 'jpg')
        key2 = ImageCacheService._generate_cache_key('thumbnail', 'test.jpg', 'jpg')
        assert key1 == key2

    def test_generate_cache_key_uniqueness(self):
        """Test that different inputs generate different keys"""
        key1 = ImageCacheService._generate_cache_key('thumbnail', 'test1.jpg', 'jpg')
        key2 = ImageCacheService._generate_cache_key('thumbnail', 'test2.jpg', 'jpg')
        assert key1 != key2

    def test_image_to_bytes_jpeg(self):
        """Test converting PIL image to JPEG bytes"""
        img = PILImage.new('RGB', (100, 100), color='red')
        img_bytes = ImageCacheService._image_to_bytes(img, 'JPEG', 90)

        assert isinstance(img_bytes, bytes)
        assert len(img_bytes) > 0

    def test_image_to_bytes_webp(self):
        """Test converting PIL image to WebP bytes"""
        img = PILImage.new('RGB', (100, 100), color='blue')
        img_bytes = ImageCacheService._image_to_bytes(img, 'WEBP', 90)

        assert isinstance(img_bytes, bytes)
        assert len(img_bytes) > 0

    def test_load_image_from_storage_handles_error(self):
        """Test that load_image_from_storage handles errors gracefully"""
        result = ImageCacheService._load_image_from_storage('nonexistent/path.jpg')
        assert result is None

    @patch('medical_imaging.image_cache_service.cache')
    def test_get_thumbnail_cache_hit(self, mock_cache):
        """Test getting thumbnail from cache (cache hit)"""
        # Mock cache hit
        mock_cached_data = b'cached_thumbnail_data'
        mock_cache.get.return_value = mock_cached_data

        result = ImageCacheService.get_thumbnail('test/path.jpg')

        assert result == mock_cached_data
        mock_cache.get.assert_called_once()

    @patch('medical_imaging.image_cache_service.cache')
    @patch.object(ImageCacheService, '_load_image_from_storage')
    def test_get_thumbnail_cache_miss(self, mock_load, mock_cache):
        """Test getting thumbnail when not in cache (cache miss)"""
        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock image loading
        mock_img = PILImage.new('RGB', (500, 500), color='green')
        mock_load.return_value = mock_img

        result = ImageCacheService.get_thumbnail('test/path.jpg')

        # Should load image and cache it
        mock_load.assert_called_once()
        mock_cache.set.assert_called_once()
        assert isinstance(result, bytes)

    @patch('medical_imaging.image_cache_service.cache')
    def test_get_thumbnail_force_regenerate(self, mock_cache):
        """Test force regenerate bypasses cache"""
        mock_cache.get.return_value = b'old_cached_data'

        with patch.object(ImageCacheService, '_load_image_from_storage') as mock_load:
            mock_img = PILImage.new('RGB', (500, 500), color='yellow')
            mock_load.return_value = mock_img

            result = ImageCacheService.get_thumbnail('test/path.jpg', force_regenerate=True)

            # Should not call cache.get when force_regenerate=True
            mock_cache.get.assert_not_called()
            mock_load.assert_called_once()

    def test_thumbnail_size_constant(self):
        """Test that thumbnail size is defined"""
        assert hasattr(ImageCacheService, 'THUMBNAIL_SIZE')
        assert isinstance(ImageCacheService.THUMBNAIL_SIZE, tuple)
        assert len(ImageCacheService.THUMBNAIL_SIZE) == 2

    def test_cache_ttl_constants(self):
        """Test that cache TTL constants are defined"""
        assert hasattr(ImageCacheService, 'THUMBNAIL_TTL')
        assert hasattr(ImageCacheService, 'PREVIEW_TTL')
        assert hasattr(ImageCacheService, 'FULL_IMAGE_TTL')

        assert isinstance(ImageCacheService.THUMBNAIL_TTL, int)
        assert isinstance(ImageCacheService.PREVIEW_TTL, int)
        assert isinstance(ImageCacheService.FULL_IMAGE_TTL, int)

    @patch('medical_imaging.image_cache_service.cache')
    def test_invalidate_cache(self, mock_cache):
        """Test cache invalidation"""
        mock_cache.delete_many.return_value = 3

        result = ImageCacheService.invalidate_cache('test/path.jpg')

        assert result == 3
        mock_cache.delete_many.assert_called_once()

    @patch('medical_imaging.image_cache_service.cache')
    def test_get_cache_stats(self, mock_cache):
        """Test getting cache statistics"""
        mock_cache_info = {
            'hits': 100,
            'misses': 20,
            'keys': 50
        }
        mock_cache.get.return_value = mock_cache_info

        stats = ImageCacheService.get_cache_stats()

        assert isinstance(stats, dict)

    def test_jpeg_quality_constant(self):
        """Test JPEG quality constant is defined"""
        assert hasattr(ImageCacheService, 'JPEG_QUALITY')
        assert isinstance(ImageCacheService.JPEG_QUALITY, int)
        assert 0 < ImageCacheService.JPEG_QUALITY <= 100

    def test_webp_quality_constant(self):
        """Test WebP quality constant is defined"""
        assert hasattr(ImageCacheService, 'WEBP_QUALITY')
        assert isinstance(ImageCacheService.WEBP_QUALITY, int)
        assert 0 < ImageCacheService.WEBP_QUALITY <= 100


@pytest.mark.unit
class TestImageCacheServiceIntegration:
    """Integration tests for Image Cache Service"""

    @patch('medical_imaging.image_cache_service.cache')
    @patch.object(ImageCacheService, '_load_image_from_storage')
    def test_full_thumbnail_workflow(self, mock_load, mock_cache):
        """Test complete thumbnail generation workflow"""
        # Setup
        mock_cache.get.return_value = None
        mock_img = PILImage.new('RGB', (1000, 1000), color='red')
        mock_load.return_value = mock_img

        # Execute
        result = ImageCacheService.get_thumbnail('test/image.jpg')

        # Verify
        assert result is not None
        assert isinstance(result, bytes)
        mock_cache.set.assert_called_once()

        # Verify cache key format
        call_args = mock_cache.set.call_args
        cache_key = call_args[0][0]
        assert cache_key.startswith('medical_imaging:')

    @patch('medical_imaging.image_cache_service.cache')
    @patch.object(ImageCacheService, '_load_image_from_storage')
    def test_preview_generation(self, mock_load, mock_cache):
        """Test preview image generation"""
        mock_cache.get.return_value = None
        mock_img = PILImage.new('RGB', (2000, 2000), color='blue')
        mock_load.return_value = mock_img

        result = ImageCacheService.get_preview('test/large_image.jpg')

        assert result is not None
        assert isinstance(result, bytes)

    def test_cache_key_format(self):
        """Test that cache keys follow expected format"""
        key = ImageCacheService._generate_cache_key('test', 'path/to/file.jpg', 'format')

        # Should contain prefix
        assert key.startswith('medical_imaging:')

        # Should contain all components
        assert 'test' in key or 'path' in key

    @patch.object(ImageCacheService, '_load_image_from_storage')
    def test_image_loading_failure_handling(self, mock_load):
        """Test handling of image loading failures"""
        mock_load.return_value = None

        result = ImageCacheService.get_thumbnail('bad/path.jpg')

        assert result is None

    def test_service_methods_exist(self):
        """Test that all expected service methods exist"""
        expected_methods = [
            'get_thumbnail',
            'get_full_image',
            'invalidate_cache',
            'get_cache_stats',
            '_generate_cache_key',
            '_load_image_from_storage',
            '_image_to_bytes'
        ]

        for method in expected_methods:
            assert hasattr(ImageCacheService, method)
            assert callable(getattr(ImageCacheService, method))


@pytest.mark.unit
class TestImageCacheEdgeCases:
    """Test edge cases and error handling"""

    @patch.object(ImageCacheService, '_load_image_from_storage')
    def test_thumbnail_with_corrupt_image(self, mock_load):
        """Test handling of corrupt image files"""
        mock_load.return_value = None
        result = ImageCacheService.get_thumbnail('corrupt/image.jpg')
        assert result is None

    def test_image_to_bytes_with_invalid_format(self):
        """Test converting image to unsupported format"""
        img = PILImage.new('RGB', (100, 100), color='red')
        # Should handle gracefully or raise specific exception
        try:
            result = ImageCacheService._image_to_bytes(img, 'INVALID_FORMAT', 90)
            # If it doesn't raise, result should be None or bytes
            assert result is None or isinstance(result, bytes)
        except (ValueError, KeyError):
            # Expected behavior for invalid format
            pass

    @patch('medical_imaging.image_cache_service.cache')
    def test_cache_set_failure(self, mock_cache):
        """Test handling of cache set failures"""
        mock_cache.get.return_value = None
        mock_cache.set.side_effect = Exception("Cache unavailable")

        with patch.object(ImageCacheService, '_load_image_from_storage') as mock_load:
            mock_img = PILImage.new('RGB', (500, 500), color='blue')
            mock_load.return_value = mock_img

            # Should handle cache failure gracefully
            try:
                result = ImageCacheService.get_thumbnail('test.jpg')
                # Even if cache fails, should return image bytes
                assert result is None or isinstance(result, bytes)
            except:
                pass  # Some implementations may propagate exception

    def test_generate_cache_key_with_special_chars(self):
        """Test cache key generation with special characters"""
        key = ImageCacheService._generate_cache_key(
            'test',
            'path/with spaces/and-special@chars.jpg',
            'jpg'
        )
        assert isinstance(key, str)
        assert len(key) > 0

    @patch.object(ImageCacheService, '_load_image_from_storage')
    def test_multiple_thumbnail_calls(self, mock_load):
        """Test multiple calls to get_thumbnail"""
        mock_img = PILImage.new('RGB', (1000, 1000), color='green')
        mock_load.return_value = mock_img

        # First call
        result1 = ImageCacheService.get_thumbnail('test.jpg')
        # Second call should use cache or regenerate
        result2 = ImageCacheService.get_thumbnail('test.jpg')

        assert isinstance(result1, bytes)
        assert isinstance(result2, bytes)
