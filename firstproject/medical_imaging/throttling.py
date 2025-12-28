"""
Custom throttling classes for rate limiting API requests.

Rate limiting is essential for:
- Preventing abuse and DoS attacks
- Protecting server resources
- Ensuring fair usage across users
- Complying with infrastructure limits (S3, Celery workers, etc.)
"""
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class BurstRateThrottle(UserRateThrottle):
    """
    Throttle for short bursts of requests.

    Prevents users from making too many requests in a short time window.
    Useful for protecting against accidental DoS (e.g., refresh spam).

    Rate: 60 requests per minute
    """
    scope = 'burst'


class SustainedRateThrottle(UserRateThrottle):
    """
    Throttle for sustained usage over longer periods.

    Prevents users from exceeding daily quotas.
    Useful for limiting heavy users and ensuring fair resource distribution.

    Rate: 1000 requests per day
    """
    scope = 'sustained'


class UploadRateThrottle(UserRateThrottle):
    """
    Strict throttle for file upload endpoints.

    File uploads are resource-intensive (CPU, memory, S3, Celery workers).
    This prevents abuse and ensures backend stability.

    Rate: 20 uploads per hour

    Use on endpoints like:
    - /api/studies/{id}/upload_images/
    - /api/patients/{id}/upload_report/
    """
    scope = 'upload'
    rate = '20/hour'

    def get_cache_key(self, request, view):
        """
        Override to use user ID + endpoint for rate limiting.

        This allows different upload endpoints to have independent limits.
        """
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }


class AIQueryRateThrottle(UserRateThrottle):
    """
    Throttle for AI/LLM chat endpoints.

    AI queries are expensive (OpenAI API costs, Anthropic costs).
    This prevents cost overruns and ensures budget control.

    Rate: 50 queries per hour

    Use on:
    - /api/ai/chat/
    - /api/ai/chat/stream/
    """
    scope = 'ai_query'
    rate = '50/hour'


class HealthCheckRateThrottle(AnonRateThrottle):
    """
    Liberal throttle for health check endpoints.

    Health checks should be frequent (Kubernetes checks every 5-10s).
    This prevents malicious actors from spamming health endpoints.

    Rate: 1000 requests per minute (very high)

    Use on:
    - /api/health/
    - /api/health/liveness/
    - /api/health/readiness/
    """
    scope = 'health'
    rate = '1000/minute'


class ContactFormRateThrottle(AnonRateThrottle):
    """
    Strict throttle for public contact forms.

    Contact forms are public and prone to spam.
    This prevents spam bots and ensures legitimate usage.

    Rate: 5 submissions per hour

    Use on:
    - /api/contact/
    """
    scope = 'contact'
    rate = '5/hour'
