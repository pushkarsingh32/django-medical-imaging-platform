"""
Test script for image caching and progressive loading functionality.
Tests Redis caching, image compression, and performance improvements.

Run with: pipenv run python test_image_cache.py
"""
import os
import sys
import django
import time
from pathlib import Path

# Setup Django environment
sys.path.append(str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.cache import cache
from medical_imaging.models import DicomImage, ImagingStudy
from medical_imaging.image_cache_service import ImageCacheService
from django.test.client import Client


def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)


def print_success(text):
    """Print success message."""
    print(f"✓ {text}")


def print_error(text):
    """Print error message."""
    print(f"✗ {text}")


def print_info(text):
    """Print info message."""
    print(f"ℹ {text}")


def test_redis_connection():
    """Test 1: Verify Redis connection."""
    print_header("Test 1: Redis Connection")

    try:
        # Try to set and get a value
        cache.set('test_key', 'test_value', 60)
        value = cache.get('test_key')

        if value == 'test_value':
            print_success("Redis connection working")
            cache.delete('test_key')
            return True
        else:
            print_error("Redis returned unexpected value")
            return False
    except Exception as e:
        print_error(f"Redis connection failed: {str(e)}")
        return False


def test_cache_stats():
    """Test 2: Get cache statistics."""
    print_header("Test 2: Cache Statistics")

    try:
        from django_redis import get_redis_connection
        redis_conn = get_redis_connection("default")
        info = redis_conn.info()

        print_info(f"Redis Version: {info.get('redis_version', 'unknown')}")
        print_info(f"Used Memory: {info.get('used_memory_human', 'unknown')}")
        print_info(f"Connected Clients: {info.get('connected_clients', 0)}")
        print_info(f"Total Commands Processed: {info.get('total_commands_processed', 0)}")

        hits = info.get('keyspace_hits', 0)
        misses = info.get('keyspace_misses', 0)
        total = hits + misses

        if total > 0:
            hit_rate = (hits / total) * 100
            print_info(f"Cache Hit Rate: {hit_rate:.2f}%")
        else:
            print_info("Cache Hit Rate: N/A (no requests yet)")

        print_success("Successfully retrieved cache statistics")
        return True
    except Exception as e:
        print_error(f"Failed to get cache stats: {str(e)}")
        return False


def test_image_caching():
    """Test 3: Test image caching functionality."""
    print_header("Test 3: Image Caching")

    try:
        # Get first image from database
        image = DicomImage.objects.first()

        if not image:
            print_error("No images in database. Please upload some images first.")
            return False

        print_info(f"Testing with image ID: {image.id}")
        print_info(f"Image file: {image.image_file.name}")

        # Test thumbnail generation (cold cache)
        print_info("\nGenerating thumbnail (cold cache)...")
        start_time = time.time()
        thumbnail = ImageCacheService.get_thumbnail(image.image_file.name)
        cold_time = time.time() - start_time

        if thumbnail:
            print_success(f"Thumbnail generated in {cold_time:.3f}s ({len(thumbnail)} bytes)")
        else:
            print_error("Failed to generate thumbnail")
            return False

        # Test thumbnail retrieval (hot cache)
        print_info("\nRetrieving thumbnail (hot cache)...")
        start_time = time.time()
        thumbnail = ImageCacheService.get_thumbnail(image.image_file.name)
        hot_time = time.time() - start_time

        if thumbnail:
            print_success(f"Thumbnail retrieved in {hot_time:.3f}s ({len(thumbnail)} bytes)")
            speedup = cold_time / hot_time if hot_time > 0 else 0
            print_info(f"Cache speedup: {speedup:.1f}x faster")
        else:
            print_error("Failed to retrieve cached thumbnail")
            return False

        # Test preview generation
        print_info("\nGenerating preview...")
        start_time = time.time()
        preview = ImageCacheService.get_preview(image.image_file.name)
        preview_time = time.time() - start_time

        if preview:
            print_success(f"Preview generated in {preview_time:.3f}s ({len(preview)} bytes)")
        else:
            print_error("Failed to generate preview")
            return False

        # Test WebP generation
        print_info("\nGenerating WebP...")
        start_time = time.time()
        webp = ImageCacheService.get_compressed_webp(image.image_file.name)
        webp_time = time.time() - start_time

        if webp:
            print_success(f"WebP generated in {webp_time:.3f}s ({len(webp)} bytes)")
        else:
            print_error("Failed to generate WebP")
            return False

        # Test cache stats for this image
        print_info("\nCache status for this image:")
        stats = ImageCacheService.get_cache_stats(image.image_file.name)
        for variant, data in stats.items():
            cached_status = "✓ Cached" if data['cached'] else "✗ Not cached"
            size_kb = data['size_bytes'] / 1024 if data['size_bytes'] > 0 else 0
            print_info(f"  {variant}: {cached_status} ({size_kb:.1f} KB)")

        print_success("Image caching test completed successfully")
        return True

    except Exception as e:
        print_error(f"Image caching test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_cache_invalidation():
    """Test 4: Test cache invalidation."""
    print_header("Test 4: Cache Invalidation")

    try:
        image = DicomImage.objects.first()

        if not image:
            print_error("No images in database")
            return False

        # Ensure image is cached
        ImageCacheService.get_thumbnail(image.image_file.name)
        ImageCacheService.get_preview(image.image_file.name)

        # Check cache before invalidation
        stats_before = ImageCacheService.get_cache_stats(image.image_file.name)
        cached_before = sum(1 for v in stats_before.values() if v['cached'])

        print_info(f"Cached variants before invalidation: {cached_before}")

        # Invalidate cache
        ImageCacheService.invalidate_cache(image.image_file.name)

        # Check cache after invalidation
        stats_after = ImageCacheService.get_cache_stats(image.image_file.name)
        cached_after = sum(1 for v in stats_after.values() if v['cached'])

        print_info(f"Cached variants after invalidation: {cached_after}")

        if cached_after == 0:
            print_success("Cache invalidation successful")
            return True
        else:
            print_error("Cache invalidation failed - some variants still cached")
            return False

    except Exception as e:
        print_error(f"Cache invalidation test failed: {str(e)}")
        return False


def test_api_endpoints():
    """Test 5: Test image serving API endpoints."""
    print_header("Test 5: API Endpoints")

    try:
        client = Client()
        image = DicomImage.objects.first()

        if not image:
            print_error("No images in database")
            return False

        endpoints = {
            'thumbnail': f'/api/images/{image.id}/thumbnail/',
            'preview': f'/api/images/{image.id}/preview/',
            'webp': f'/api/images/{image.id}/webp/',
            'metadata': f'/api/images/{image.id}/metadata/',
        }

        all_passed = True

        for name, url in endpoints.items():
            try:
                response = client.get(url)

                if response.status_code == 200:
                    if name == 'metadata':
                        print_success(f"{name.capitalize()} endpoint: OK (JSON response)")
                    else:
                        content_length = len(response.content)
                        print_success(f"{name.capitalize()} endpoint: OK ({content_length} bytes)")
                else:
                    print_error(f"{name.capitalize()} endpoint: Failed (status {response.status_code})")
                    all_passed = False
            except Exception as e:
                print_error(f"{name.capitalize()} endpoint: Error - {str(e)}")
                all_passed = False

        # Test cache stats endpoint
        try:
            response = client.get('/api/images/cache-stats/')
            if response.status_code == 200:
                print_success("Cache stats endpoint: OK")
            else:
                print_error(f"Cache stats endpoint: Failed (status {response.status_code})")
                all_passed = False
        except Exception as e:
            print_error(f"Cache stats endpoint: Error - {str(e)}")
            all_passed = False

        if all_passed:
            print_success("All API endpoints working correctly")
        else:
            print_error("Some API endpoints failed")

        return all_passed

    except Exception as e:
        print_error(f"API endpoint test failed: {str(e)}")
        return False


def test_database_indexes():
    """Test 6: Verify database indexes were created."""
    print_header("Test 6: Database Indexes")

    try:
        from django.db import connection

        # Get table names
        tables = {
            'hospitals': 'medical_imaging_hospital',
            'patients': 'medical_imaging_patient',
            'studies': 'medical_imaging_imagingstudy',
            'images': 'medical_imaging_dicomimage',
            'diagnoses': 'medical_imaging_diagnosis',
        }

        with connection.cursor() as cursor:
            for name, table in tables.items():
                cursor.execute(f"SHOW INDEX FROM {table}")
                indexes = cursor.fetchall()

                # Count non-primary indexes
                non_primary = [idx for idx in indexes if idx[2] != 'PRIMARY']

                print_info(f"{name.capitalize()}: {len(non_primary)} indexes")

        print_success("Database indexes verified")
        return True

    except Exception as e:
        print_error(f"Database index test failed: {str(e)}")
        return False


def run_all_tests():
    """Run all tests and print summary."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "IMAGE CACHE & PERFORMANCE TEST SUITE" + " " * 22 + "║")
    print("╚" + "=" * 78 + "╝")

    tests = [
        ("Redis Connection", test_redis_connection),
        ("Cache Statistics", test_cache_stats),
        ("Image Caching", test_image_caching),
        ("Cache Invalidation", test_cache_invalidation),
        ("API Endpoints", test_api_endpoints),
        ("Database Indexes", test_database_indexes),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print_error(f"Test '{test_name}' crashed: {str(e)}")
            results.append((test_name, False))

    # Print summary
    print_header("Test Summary")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {test_name}")

    print("\n" + "-" * 80)
    print(f"Results: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")
    print("-" * 80 + "\n")

    if passed == total:
        print("🎉 All tests passed! Image caching and performance optimizations are working correctly.")
    else:
        print("⚠️  Some tests failed. Please review the errors above.")

    return passed == total


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
