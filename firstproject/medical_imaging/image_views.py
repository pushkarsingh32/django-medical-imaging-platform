"""
Optimized image serving views with caching and progressive loading.
"""
import logging
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .models import DicomImage
from .image_cache_service import ImageCacheService

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def serve_thumbnail(request, image_id):
    """
    Serve a thumbnail version of an image (200x200).
    This is cached in Redis for fast subsequent access.

    Usage: GET /api/images/{image_id}/thumbnail/
    """
    try:
        # Get the image object
        image = DicomImage.objects.select_related('study').get(id=image_id)

        # Get thumbnail from cache or generate
        thumbnail_bytes = ImageCacheService.get_thumbnail(image.image_file.name)

        if not thumbnail_bytes:
            return HttpResponse(
                "Error generating thumbnail",
                status=500,
                content_type='text/plain'
            )

        # Return thumbnail with appropriate headers
        response = HttpResponse(thumbnail_bytes, content_type='image/jpeg')
        response['Content-Disposition'] = f'inline; filename="thumbnail_{image_id}.jpg"'
        response['Cache-Control'] = 'public, max-age=86400'  # Cache for 24 hours
        response['X-Cache-Source'] = 'redis'

        return response

    except DicomImage.DoesNotExist:
        return HttpResponse("Image not found", status=404, content_type='text/plain')
    except Exception as e:
        logger.error(f"Error serving thumbnail for image {image_id}: {str(e)}")
        return HttpResponse(
            "Internal server error",
            status=500,
            content_type='text/plain'
        )


@require_http_methods(["GET"])
def serve_preview(request, image_id):
    """
    Serve a preview version of an image (800x800).
    Good balance between quality and file size.

    Usage: GET /api/images/{image_id}/preview/
    """
    try:
        # Get the image object
        image = DicomImage.objects.select_related('study').get(id=image_id)

        # Get preview from cache or generate
        preview_bytes = ImageCacheService.get_preview(image.image_file.name)

        if not preview_bytes:
            return HttpResponse(
                "Error generating preview",
                status=500,
                content_type='text/plain'
            )

        # Return preview with appropriate headers
        response = HttpResponse(preview_bytes, content_type='image/jpeg')
        response['Content-Disposition'] = f'inline; filename="preview_{image_id}.jpg"'
        response['Cache-Control'] = 'public, max-age=7200'  # Cache for 2 hours
        response['X-Cache-Source'] = 'redis'

        return response

    except DicomImage.DoesNotExist:
        return HttpResponse("Image not found", status=404, content_type='text/plain')
    except Exception as e:
        logger.error(f"Error serving preview for image {image_id}: {str(e)}")
        return HttpResponse(
            "Internal server error",
            status=500,
            content_type='text/plain'
        )


@require_http_methods(["GET"])
def serve_webp(request, image_id):
    """
    Serve a WebP compressed version of an image.
    WebP provides better compression than JPEG for modern browsers.

    Usage: GET /api/images/{image_id}/webp/
    """
    try:
        # Get the image object
        image = DicomImage.objects.select_related('study').get(id=image_id)

        # Get WebP from cache or generate
        webp_bytes = ImageCacheService.get_compressed_webp(image.image_file.name)

        if not webp_bytes:
            return HttpResponse(
                "Error generating WebP",
                status=500,
                content_type='text/plain'
            )

        # Return WebP with appropriate headers
        response = HttpResponse(webp_bytes, content_type='image/webp')
        response['Content-Disposition'] = f'inline; filename="{image_id}.webp"'
        response['Cache-Control'] = 'public, max-age=7200'  # Cache for 2 hours
        response['X-Cache-Source'] = 'redis'

        return response

    except DicomImage.DoesNotExist:
        return HttpResponse("Image not found", status=404, content_type='text/plain')
    except Exception as e:
        logger.error(f"Error serving WebP for image {image_id}: {str(e)}")
        return HttpResponse(
            "Internal server error",
            status=500,
            content_type='text/plain'
        )


@require_http_methods(["GET"])
def serve_full_image(request, image_id):
    """
    Serve the full-quality original image with caching.
    This should be loaded on-demand (not automatically).

    Usage: GET /api/images/{image_id}/full/
    """
    try:
        # Get the image object
        image = DicomImage.objects.select_related('study').get(id=image_id)

        # Get full image from cache or storage
        image_bytes = ImageCacheService.get_full_image(image.image_file.name)

        if not image_bytes:
            return HttpResponse(
                "Error loading image",
                status=500,
                content_type='text/plain'
            )

        # Determine content type from file extension
        content_type = 'image/jpeg'  # Default
        if image.image_file.name.lower().endswith('.png'):
            content_type = 'image/png'
        elif image.image_file.name.lower().endswith('.webp'):
            content_type = 'image/webp'

        # Return full image with appropriate headers
        response = HttpResponse(image_bytes, content_type=content_type)
        response['Content-Disposition'] = f'inline; filename="full_{image_id}.jpg"'
        response['Cache-Control'] = 'public, max-age=3600'  # Cache for 1 hour
        response['X-Cache-Source'] = 'redis'

        return response

    except DicomImage.DoesNotExist:
        return HttpResponse("Image not found", status=404, content_type='text/plain')
    except Exception as e:
        logger.error(f"Error serving full image {image_id}: {str(e)}")
        return HttpResponse(
            "Internal server error",
            status=500,
            content_type='text/plain'
        )


@api_view(['GET'])
def image_metadata(request, image_id):
    """
    Get metadata about an image including cache status.
    Useful for debugging and monitoring.

    Usage: GET /api/images/{image_id}/metadata/

    Returns:
        {
            "id": 123,
            "file_name": "scan.jpg",
            "file_size": 1048576,
            "cache_status": {
                "thumbnail": {"cached": true, "size_bytes": 15000},
                "preview": {"cached": false, "size_bytes": 0},
                "webp": {"cached": true, "size_bytes": 50000},
                "full": {"cached": true, "size_bytes": 1048576}
            }
        }
    """
    try:
        # Get the image object
        image = DicomImage.objects.select_related('study', 'study__patient').get(id=image_id)

        # Get cache stats
        cache_stats = ImageCacheService.get_cache_stats(image.image_file.name)

        # Build metadata response
        metadata = {
            "id": image.id,
            "file_name": image.image_file.name.split('/')[-1],
            "file_path": image.image_file.name,
            "file_size": image.image_file.size if hasattr(image.image_file, 'size') else 0,
            "study_id": image.study.id,
            "patient_name": image.study.patient.full_name,
            "cache_status": cache_stats,
            "urls": {
                "thumbnail": f"/api/images/{image_id}/thumbnail/",
                "preview": f"/api/images/{image_id}/preview/",
                "webp": f"/api/images/{image_id}/webp/",
                "full": f"/api/images/{image_id}/full/",
            }
        }

        return Response(metadata)

    except DicomImage.DoesNotExist:
        return Response({"error": "Image not found"}, status=404)
    except Exception as e:
        logger.error(f"Error getting metadata for image {image_id}: {str(e)}")
        return Response({"error": "Internal server error"}, status=500)


@api_view(['POST'])
def invalidate_cache(request, image_id):
    """
    Invalidate all cached versions of an image.
    Useful when an image is updated.

    Usage: POST /api/images/{image_id}/invalidate-cache/
    """
    try:
        # Get the image object
        image = DicomImage.objects.get(id=image_id)

        # Invalidate cache
        ImageCacheService.invalidate_cache(image.image_file.name)

        return Response({
            "success": True,
            "message": f"Cache invalidated for image {image_id}"
        })

    except DicomImage.DoesNotExist:
        return Response({"error": "Image not found"}, status=404)
    except Exception as e:
        logger.error(f"Error invalidating cache for image {image_id}: {str(e)}")
        return Response({"error": "Internal server error"}, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def cache_statistics(request):
    """
    Get overall cache statistics.
    Shows how well the cache is performing.

    Usage: GET /api/images/cache-stats/

    Returns cache hit/miss rates and memory usage.
    """
    from django.core.cache import cache

    try:
        # Get Redis cache stats
        # Note: This requires django-redis backend
        cache_backend = cache._cache

        stats = {
            "backend": "redis",
            "host": cache_backend.client.connection_pool.connection_kwargs.get('host', 'unknown'),
            "db": cache_backend.client.connection_pool.connection_kwargs.get('db', 0),
        }

        # Try to get Redis INFO if available
        try:
            from django_redis import get_redis_connection
            redis_conn = get_redis_connection("default")
            info = redis_conn.info()

            stats.update({
                "redis_version": info.get('redis_version', 'unknown'),
                "used_memory": info.get('used_memory_human', 'unknown'),
                "connected_clients": info.get('connected_clients', 0),
                "total_commands_processed": info.get('total_commands_processed', 0),
                "keyspace_hits": info.get('keyspace_hits', 0),
                "keyspace_misses": info.get('keyspace_misses', 0),
            })

            # Calculate hit rate
            hits = info.get('keyspace_hits', 0)
            misses = info.get('keyspace_misses', 0)
            total = hits + misses

            if total > 0:
                stats['hit_rate'] = f"{(hits / total * 100):.2f}%"
            else:
                stats['hit_rate'] = "N/A"

        except Exception as e:
            logger.warning(f"Could not get Redis INFO: {str(e)}")

        return Response(stats)

    except Exception as e:
        logger.error(f"Error getting cache statistics: {str(e)}")
        return Response({"error": "Could not retrieve cache statistics"}, status=500)
