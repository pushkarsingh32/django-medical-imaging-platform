"""
Image caching and compression service for medical imaging.
Provides:
- Redis caching for frequently accessed images
- Progressive image loading (thumbnails + full quality)
- Image compression (DICOM to JPEG/WebP)
- Performance optimization for large DICOM files
"""
import hashlib
import io
import logging
from typing import Optional, Tuple
from PIL import Image
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from decouple import config

logger = logging.getLogger(__name__)


class ImageCacheService:
    """Service for caching and optimizing medical images."""

    # Cache key prefixes
    THUMBNAIL_PREFIX = "img_thumb"
    FULL_IMAGE_PREFIX = "img_full"
    COMPRESSED_PREFIX = "img_comp"

    # Image sizes
    THUMBNAIL_SIZE = (200, 200)
    PREVIEW_SIZE = (800, 800)

    # Compression quality
    JPEG_QUALITY = 85
    WEBP_QUALITY = 80

    # Cache TTLs (in seconds)
    THUMBNAIL_TTL = 86400  # 24 hours
    FULL_IMAGE_TTL = 3600   # 1 hour
    COMPRESSED_TTL = 7200   # 2 hours

    @staticmethod
    def _generate_cache_key(prefix: str, file_path: str, size: Optional[str] = None) -> str:
        """
        Generate a unique cache key for an image.

        Args:
            prefix: Cache key prefix
            file_path: Path to the image file
            size: Optional size descriptor (e.g., 'thumbnail', 'preview')

        Returns:
            str: Cache key
        """
        # Create a hash of the file path for consistent keys
        path_hash = hashlib.md5(file_path.encode()).hexdigest()

        if size:
            return f"{prefix}:{path_hash}:{size}"
        return f"{prefix}:{path_hash}"

    @staticmethod
    def _load_image_from_storage(file_path: str) -> Optional[Image.Image]:
        """
        Load an image from storage (S3 or local).

        Args:
            file_path: Path to the image file

        Returns:
            PIL.Image or None if loading fails
        """
        try:
            # Open file from storage
            with default_storage.open(file_path, 'rb') as f:
                image_data = f.read()

            # Open with PIL
            image = Image.open(io.BytesIO(image_data))

            # Convert to RGB if necessary (DICOM files might be grayscale)
            if image.mode not in ('RGB', 'RGBA'):
                image = image.convert('RGB')

            return image
        except Exception as e:
            logger.error(f"Error loading image from {file_path}: {str(e)}")
            return None

    @staticmethod
    def _image_to_bytes(image: Image.Image, format: str = 'JPEG', quality: int = 85) -> bytes:
        """
        Convert PIL Image to bytes.

        Args:
            image: PIL Image object
            format: Image format (JPEG, PNG, WEBP)
            quality: Compression quality (1-100)

        Returns:
            bytes: Compressed image data
        """
        buffer = io.BytesIO()

        # Save with appropriate settings
        save_kwargs = {'format': format}

        if format in ('JPEG', 'WEBP'):
            save_kwargs['quality'] = quality
            save_kwargs['optimize'] = True

        image.save(buffer, **save_kwargs)
        return buffer.getvalue()

    @classmethod
    def get_thumbnail(cls, file_path: str, force_regenerate: bool = False) -> Optional[bytes]:
        """
        Get or generate a thumbnail for an image.

        Args:
            file_path: Path to the original image
            force_regenerate: Force regeneration even if cached

        Returns:
            bytes: Thumbnail image data (JPEG format)
        """
        cache_key = cls._generate_cache_key(cls.THUMBNAIL_PREFIX, file_path, 'thumb')

        # Try to get from cache
        if not force_regenerate:
            cached_thumbnail = cache.get(cache_key)
            if cached_thumbnail:
                logger.debug(f"Thumbnail cache HIT for {file_path}")
                return cached_thumbnail

        logger.debug(f"Thumbnail cache MISS for {file_path}")

        # Load original image
        image = cls._load_image_from_storage(file_path)
        if not image:
            return None

        # Generate thumbnail
        image.thumbnail(cls.THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

        # Convert to bytes
        thumbnail_bytes = cls._image_to_bytes(image, 'JPEG', cls.JPEG_QUALITY)

        # Cache it
        cache.set(cache_key, thumbnail_bytes, cls.THUMBNAIL_TTL)

        logger.info(f"Generated and cached thumbnail for {file_path}")
        return thumbnail_bytes

    @classmethod
    def get_preview(cls, file_path: str, force_regenerate: bool = False) -> Optional[bytes]:
        """
        Get or generate a preview (medium size) for an image.

        Args:
            file_path: Path to the original image
            force_regenerate: Force regeneration even if cached

        Returns:
            bytes: Preview image data (JPEG format)
        """
        cache_key = cls._generate_cache_key(cls.COMPRESSED_PREFIX, file_path, 'preview')

        # Try to get from cache
        if not force_regenerate:
            cached_preview = cache.get(cache_key)
            if cached_preview:
                logger.debug(f"Preview cache HIT for {file_path}")
                return cached_preview

        logger.debug(f"Preview cache MISS for {file_path}")

        # Load original image
        image = cls._load_image_from_storage(file_path)
        if not image:
            return None

        # Resize to preview size if larger
        if image.width > cls.PREVIEW_SIZE[0] or image.height > cls.PREVIEW_SIZE[1]:
            image.thumbnail(cls.PREVIEW_SIZE, Image.Resampling.LANCZOS)

        # Convert to bytes
        preview_bytes = cls._image_to_bytes(image, 'JPEG', cls.JPEG_QUALITY)

        # Cache it
        cache.set(cache_key, preview_bytes, cls.COMPRESSED_TTL)

        logger.info(f"Generated and cached preview for {file_path}")
        return preview_bytes

    @classmethod
    def get_compressed_webp(cls, file_path: str, force_regenerate: bool = False) -> Optional[bytes]:
        """
        Get or generate a WebP compressed version of an image.
        WebP provides better compression than JPEG for web delivery.

        Args:
            file_path: Path to the original image
            force_regenerate: Force regeneration even if cached

        Returns:
            bytes: WebP image data
        """
        cache_key = cls._generate_cache_key(cls.COMPRESSED_PREFIX, file_path, 'webp')

        # Try to get from cache
        if not force_regenerate:
            cached_webp = cache.get(cache_key)
            if cached_webp:
                logger.debug(f"WebP cache HIT for {file_path}")
                return cached_webp

        logger.debug(f"WebP cache MISS for {file_path}")

        # Load original image
        image = cls._load_image_from_storage(file_path)
        if not image:
            return None

        # Convert to WebP
        webp_bytes = cls._image_to_bytes(image, 'WEBP', cls.WEBP_QUALITY)

        # Cache it
        cache.set(cache_key, webp_bytes, cls.COMPRESSED_TTL)

        logger.info(f"Generated and cached WebP for {file_path}")
        return webp_bytes

    @classmethod
    def get_full_image(cls, file_path: str) -> Optional[bytes]:
        """
        Get full-quality image with caching.
        This is for the original/highest quality version.

        Args:
            file_path: Path to the original image

        Returns:
            bytes: Full image data
        """
        cache_key = cls._generate_cache_key(cls.FULL_IMAGE_PREFIX, file_path)

        # Try to get from cache
        cached_image = cache.get(cache_key)
        if cached_image:
            logger.debug(f"Full image cache HIT for {file_path}")
            return cached_image

        logger.debug(f"Full image cache MISS for {file_path}")

        # Load from storage
        try:
            with default_storage.open(file_path, 'rb') as f:
                image_data = f.read()

            # Cache it (full images have shorter TTL to save memory)
            cache.set(cache_key, image_data, cls.FULL_IMAGE_TTL)

            logger.info(f"Cached full image for {file_path}")
            return image_data
        except Exception as e:
            logger.error(f"Error loading full image from {file_path}: {str(e)}")
            return None

    @classmethod
    def invalidate_cache(cls, file_path: str) -> None:
        """
        Invalidate all cached versions of an image.
        Call this when an image is updated or deleted.

        Args:
            file_path: Path to the image file
        """
        # Generate all possible cache keys
        keys_to_delete = [
            cls._generate_cache_key(cls.THUMBNAIL_PREFIX, file_path, 'thumb'),
            cls._generate_cache_key(cls.COMPRESSED_PREFIX, file_path, 'preview'),
            cls._generate_cache_key(cls.COMPRESSED_PREFIX, file_path, 'webp'),
            cls._generate_cache_key(cls.FULL_IMAGE_PREFIX, file_path),
        ]

        # Delete all
        cache.delete_many(keys_to_delete)
        logger.info(f"Invalidated cache for {file_path}")

    @classmethod
    def get_cache_stats(cls, file_path: str) -> dict:
        """
        Get cache statistics for an image.
        Useful for debugging and monitoring.

        Args:
            file_path: Path to the image file

        Returns:
            dict: Cache status for each variant
        """
        keys = {
            'thumbnail': cls._generate_cache_key(cls.THUMBNAIL_PREFIX, file_path, 'thumb'),
            'preview': cls._generate_cache_key(cls.COMPRESSED_PREFIX, file_path, 'preview'),
            'webp': cls._generate_cache_key(cls.COMPRESSED_PREFIX, file_path, 'webp'),
            'full': cls._generate_cache_key(cls.FULL_IMAGE_PREFIX, file_path),
        }

        stats = {}
        for variant, key in keys.items():
            cached_data = cache.get(key)
            stats[variant] = {
                'cached': cached_data is not None,
                'size_bytes': len(cached_data) if cached_data else 0,
            }

        return stats


class ImageCompressionService:
    """Service for converting DICOM to web-friendly formats."""

    @staticmethod
    def dicom_to_jpeg(dicom_file_path: str, output_path: Optional[str] = None) -> Optional[str]:
        """
        Convert DICOM file to JPEG format.
        Note: For production use with actual DICOM files, you'd use pydicom library.
        This is a simplified version that works with standard image formats.

        Args:
            dicom_file_path: Path to DICOM file
            output_path: Optional output path, if None returns bytes

        Returns:
            str: Path to saved JPEG or None
        """
        try:
            # Load image
            image = ImageCacheService._load_image_from_storage(dicom_file_path)
            if not image:
                return None

            # Convert to JPEG bytes
            jpeg_bytes = ImageCacheService._image_to_bytes(
                image, 'JPEG', ImageCacheService.JPEG_QUALITY
            )

            # Save if output path provided
            if output_path:
                with default_storage.open(output_path, 'wb') as f:
                    f.write(jpeg_bytes)
                return output_path

            return jpeg_bytes
        except Exception as e:
            logger.error(f"Error converting DICOM to JPEG: {str(e)}")
            return None

    @staticmethod
    def estimate_compression_ratio(original_size: int, compressed_size: int) -> float:
        """
        Calculate compression ratio.

        Args:
            original_size: Original file size in bytes
            compressed_size: Compressed file size in bytes

        Returns:
            float: Compression ratio (e.g., 0.3 means 70% reduction)
        """
        if original_size == 0:
            return 0.0
        return compressed_size / original_size
