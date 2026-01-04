"""
Custom middleware for django-allauth headless CSRF exemption
"""
from django.utils.decorators import decorator_from_middleware
from django.views.decorators.csrf import csrf_exempt


class DisableCSRFForAllauthMiddleware:
    """
    Disable CSRF for django-allauth headless API endpoints and AI chat.
    Django-allauth headless uses session tokens (X-Session-Token header) instead of CSRF tokens.
    AI chat endpoints use session authentication via cookies.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Exempt allauth headless endpoints and AI chat from CSRF
        # These endpoints use session authentication (cookies) instead of CSRF tokens
        if request.path.startswith('/_allauth/') or request.path.startswith('/api/ai/'):
            setattr(request, '_dont_enforce_csrf_checks', True)

        response = self.get_response(request)
        return response
