"""
System Health Check Endpoint

Production-ready health monitoring for:
- Load balancers (503 response triggers failover)
- Kubernetes liveness/readiness probes
- Monitoring systems (Datadog, New Relic, etc.)
- Operations teams

Checks:
- Database connectivity
- Redis cache connectivity
- Celery worker availability
- Storage backend (S3/local)
"""
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status as http_status
from django.db import connection
from django.core.cache import cache
from django.core.files.storage import default_storage
from celery import current_app
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample
from .throttling import HealthCheckRateThrottle
import logging

logger = logging.getLogger(__name__)


def check_database():
    """
    Check database connectivity.

    Returns:
        dict: Status and details
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return {
            'status': 'healthy',
            'details': 'Database connection successful'
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            'status': 'unhealthy',
            'details': f'Database connection failed: {str(e)}'
        }


def check_redis():
    """
    Check Redis cache connectivity.

    Returns:
        dict: Status and details
    """
    try:
        # Try to set and get a test key
        test_key = 'health_check_test'
        test_value = 'ok'

        cache.set(test_key, test_value, timeout=10)
        retrieved_value = cache.get(test_key)

        if retrieved_value == test_value:
            cache.delete(test_key)
            return {
                'status': 'healthy',
                'details': 'Redis connection successful'
            }
        else:
            return {
                'status': 'unhealthy',
                'details': 'Redis read/write validation failed'
            }
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {
            'status': 'unhealthy',
            'details': f'Redis connection failed: {str(e)}'
        }


def check_celery_workers():
    """
    Check if Celery workers are available.

    Returns:
        dict: Status and details
    """
    try:
        # Get active workers
        inspect = current_app.control.inspect()
        active_workers = inspect.active()

        if active_workers:
            worker_count = len(active_workers)
            return {
                'status': 'healthy',
                'details': f'{worker_count} Celery worker(s) active',
                'workers': list(active_workers.keys())
            }
        else:
            return {
                'status': 'unhealthy',
                'details': 'No Celery workers available'
            }
    except Exception as e:
        logger.error(f"Celery health check failed: {e}")
        return {
            'status': 'unhealthy',
            'details': f'Celery check failed: {str(e)}'
        }


def check_storage():
    """
    Check storage backend (S3 or local filesystem).

    Returns:
        dict: Status and details
    """
    try:
        # Check if storage is accessible
        # For S3: checks credentials and bucket access
        # For local: checks directory write permissions
        test_file_name = '.health_check'

        # Try to save a test file
        from django.core.files.base import ContentFile
        default_storage.save(test_file_name, ContentFile(b'health check'))

        # Try to read it back
        if default_storage.exists(test_file_name):
            default_storage.delete(test_file_name)

            storage_backend = default_storage.__class__.__name__
            return {
                'status': 'healthy',
                'details': f'Storage backend ({storage_backend}) accessible'
            }
        else:
            return {
                'status': 'unhealthy',
                'details': 'Storage write/read validation failed'
            }
    except Exception as e:
        logger.error(f"Storage health check failed: {e}")
        return {
            'status': 'unhealthy',
            'details': f'Storage check failed: {str(e)}'
        }


@extend_schema(
    summary="System Health Check",
    description="""
    Comprehensive health check endpoint for monitoring system health.

    **Rate Limit:** 1000 requests per minute (high limit for Kubernetes probes)

    **Use Cases:**
    - Load balancers: Route traffic only to healthy instances
    - Kubernetes: Liveness and readiness probes
    - Monitoring systems: Alert on 503 responses
    - Operations: Quick system status overview

    **Health Checks:**
    - Database connectivity (SELECT 1 query)
    - Redis cache (read/write test)
    - Celery workers (ping active workers)
    - Storage backend (S3 or local filesystem)

    **Status Codes:**
    - 200 OK: All systems healthy
    - 503 Service Unavailable: One or more systems unhealthy
    """,
    responses={
        200: OpenApiResponse(
            description="All systems healthy",
            examples=[
                OpenApiExample(
                    "All Healthy",
                    value={
                        "status": "healthy",
                        "checks": {
                            "database": {"status": "healthy", "details": "Database connection successful"},
                            "redis": {"status": "healthy", "details": "Redis read/write successful", "latency_ms": 5.2},
                            "celery": {"status": "healthy", "details": "3 Celery worker(s) active", "active_workers": 3},
                            "storage": {"status": "healthy", "details": "Storage backend (S3Storage) accessible"}
                        }
                    }
                )
            ]
        ),
        503: OpenApiResponse(
            description="One or more systems unhealthy",
            examples=[
                OpenApiExample(
                    "Database Down",
                    value={
                        "status": "unhealthy",
                        "checks": {
                            "database": {"status": "unhealthy", "details": "Database connection failed: connection refused"},
                            "redis": {"status": "healthy", "details": "Redis read/write successful", "latency_ms": 3.1},
                            "celery": {"status": "healthy", "details": "2 Celery worker(s) active", "active_workers": 2},
                            "storage": {"status": "healthy", "details": "Storage backend (FileSystemStorage) accessible"}
                        }
                    }
                )
            ]
        )
    },
    tags=["Health"]
)
@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([HealthCheckRateThrottle])
def health_check(request):
    """Comprehensive system health check endpoint."""
    checks = {
        'database': check_database(),
        'redis': check_redis(),
        'celery': check_celery_workers(),
        'storage': check_storage(),
    }

    # Overall status: healthy only if ALL checks pass
    all_healthy = all(
        check['status'] == 'healthy'
        for check in checks.values()
    )

    overall_status = 'healthy' if all_healthy else 'unhealthy'

    response_data = {
        'status': overall_status,
        'checks': checks
    }

    # Return 503 if unhealthy (tells load balancers to stop routing here)
    status_code = http_status.HTTP_200_OK if all_healthy else http_status.HTTP_503_SERVICE_UNAVAILABLE

    # Log unhealthy states
    if not all_healthy:
        unhealthy_services = [
            name for name, check in checks.items()
            if check['status'] == 'unhealthy'
        ]
        logger.error(
            f"Health check failed. Unhealthy services: {', '.join(unhealthy_services)}"
        )

    return Response(response_data, status=status_code)


@extend_schema(
    summary="Kubernetes Liveness Probe",
    description="""
    Liveness probe for Kubernetes orchestration.

    **Purpose:**
    Determines if the application process is alive and functioning.

    **Kubernetes Behavior:**
    - If this fails multiple times, Kubernetes RESTARTS the pod
    - Should only fail if application is deadlocked or crashed
    - Does NOT check external dependencies (DB, Redis, etc.)

    **Use in deployment.yaml:**
    ```yaml
    livenessProbe:
      httpGet:
        path: /api/health/liveness/
        port: 8000
      initialDelaySeconds: 30
      periodSeconds: 10
      failureThreshold: 3
    ```
    """,
    responses={
        200: OpenApiResponse(
            description="Application is alive",
            examples=[
                OpenApiExample(
                    "Alive",
                    value={"status": "alive"}
                )
            ]
        )
    },
    tags=["Health"]
)
@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([HealthCheckRateThrottle])
def liveness_probe(request):
    """Kubernetes liveness probe endpoint."""
    return Response({'status': 'alive'}, status=http_status.HTTP_200_OK)


@extend_schema(
    summary="Kubernetes Readiness Probe",
    description="""
    Readiness probe for Kubernetes orchestration.

    **Purpose:**
    Determines if the application is ready to serve traffic.

    **Kubernetes Behavior:**
    - If this fails, Kubernetes REMOVES pod from load balancer
    - Pod is NOT restarted (unlike liveness probe)
    - Traffic is redirected to healthy pods
    - Pod is added back when check passes

    **Checks:**
    - Database connectivity (critical)
    - Redis cache (critical)

    **Difference from Liveness:**
    - Liveness: "Is the app alive?" → Restart if failing
    - Readiness: "Can the app handle requests?" → Remove from load balancer if failing

    **Use in deployment.yaml:**
    ```yaml
    readinessProbe:
      httpGet:
        path: /api/health/readiness/
        port: 8000
      initialDelaySeconds: 10
      periodSeconds: 5
      failureThreshold: 2
    ```
    """,
    responses={
        200: OpenApiResponse(
            description="Ready to serve traffic",
            examples=[
                OpenApiExample(
                    "Ready",
                    value={
                        "status": "ready",
                        "checks": {
                            "database": {"status": "healthy", "details": "Database connection successful"},
                            "redis": {"status": "healthy", "details": "Redis read/write successful", "latency_ms": 4.1}
                        }
                    }
                )
            ]
        ),
        503: OpenApiResponse(
            description="Not ready to serve traffic",
            examples=[
                OpenApiExample(
                    "Not Ready",
                    value={
                        "status": "not_ready",
                        "checks": {
                            "database": {"status": "unhealthy", "details": "Database connection failed: timeout"},
                            "redis": {"status": "healthy", "details": "Redis read/write successful", "latency_ms": 3.8}
                        }
                    }
                )
            ]
        )
    },
    tags=["Health"]
)
@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([HealthCheckRateThrottle])
def readiness_probe(request):
    """Kubernetes readiness probe endpoint."""
    # Only check critical services for readiness
    db_check = check_database()
    redis_check = check_redis()

    ready = (
        db_check['status'] == 'healthy' and
        redis_check['status'] == 'healthy'
    )

    status_code = http_status.HTTP_200_OK if ready else http_status.HTTP_503_SERVICE_UNAVAILABLE

    return Response({
        'status': 'ready' if ready else 'not_ready',
        'checks': {
            'database': db_check,
            'redis': redis_check
        }
    }, status=status_code)
