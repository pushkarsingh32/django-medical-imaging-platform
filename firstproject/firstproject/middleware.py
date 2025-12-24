"""
Custom middleware for django-allauth headless CSRF exemption
"""
from django.utils.decorators import decorator_from_middleware
from django.views.decorators.csrf import csrf_exempt


class DisableCSRFForAllauthMiddleware:
    """
    Disable CSRF for django-allauth headless API endpoints.
    Django-allauth headless uses session tokens (X-Session-Token header) instead of CSRF tokens.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Exempt allauth headless endpoints from CSRF
        if request.path.startswith('/_allauth/'):
            setattr(request, '_dont_enforce_csrf_checks', True)

        response = self.get_response(request)
        return response
