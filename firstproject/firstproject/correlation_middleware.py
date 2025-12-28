"""
Correlation ID Middleware for Distributed Tracing

Provides end-to-end request tracing across:
- HTTP requests (Django views)
- Celery background tasks
- Audit logs
- Application logs

Usage:
    Every request gets a unique correlation ID that can be traced
    through the entire system lifecycle.
"""
import uuid
import logging
from contextvars import ContextVar

# Thread-safe context variable for correlation ID
correlation_id_context: ContextVar[str] = ContextVar('correlation_id', default=None)

logger = logging.getLogger(__name__)


def get_correlation_id():
    """
    Get the current correlation ID from context.

    Returns:
        str: Current correlation ID or None if not set
    """
    return correlation_id_context.get(None)


def set_correlation_id(correlation_id):
    """
    Set the correlation ID in the current context.

    Args:
        correlation_id (str): The correlation ID to set
    """
    correlation_id_context.set(correlation_id)


class CorrelationIdMiddleware:
    """
    Django middleware that extracts or generates correlation IDs for request tracing.

    How it works:
    1. Checks for X-Correlation-ID header from client
    2. If not present, generates a new UUID
    3. Sets correlation ID in thread-local context
    4. Adds correlation ID to response headers
    5. Adds correlation ID to log context

    This enables:
    - Tracing requests across microservices
    - Debugging distributed workflows
    - HIPAA compliance (full audit trail)
    - Production troubleshooting
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Extract or generate correlation ID
        correlation_id = request.headers.get('X-Correlation-ID')

        if not correlation_id:
            # Generate new UUID for this request
            correlation_id = str(uuid.uuid4())

        # Set in context for this request thread
        set_correlation_id(correlation_id)

        # Add to request object for easy access
        request.correlation_id = correlation_id

        # Log request with correlation ID
        logger.info(
            f"Request started: {request.method} {request.path}",
            extra={'correlation_id': correlation_id}
        )

        # Process request
        response = self.get_response(request)

        # Add correlation ID to response headers
        # Client can use this to correlate with their logs
        response['X-Correlation-ID'] = correlation_id

        # Log response
        logger.info(
            f"Request completed: {request.method} {request.path} -> {response.status_code}",
            extra={'correlation_id': correlation_id}
        )

        return response

    def process_exception(self, request, exception):
        """
        Log exceptions with correlation ID for debugging.
        """
        correlation_id = getattr(request, 'correlation_id', None)
        if correlation_id:
            logger.error(
                f"Request failed: {request.method} {request.path} - {str(exception)}",
                extra={'correlation_id': correlation_id},
                exc_info=True
            )
        return None


class CorrelationIdLoggingFilter(logging.Filter):
    """
    Logging filter that adds correlation ID to all log records.

    Usage in settings.py:
        LOGGING = {
            'filters': {
                'correlation_id': {
                    '()': 'firstproject.correlation_middleware.CorrelationIdLoggingFilter'
                }
            },
            'formatters': {
                'verbose': {
                    'format': '[%(correlation_id)s] %(levelname)s %(name)s: %(message)s'
                }
            }
        }
    """

    def filter(self, record):
        """
        Add correlation_id to log record.
        """
        correlation_id = get_correlation_id()
        record.correlation_id = correlation_id or 'NO-CID'
        return True
