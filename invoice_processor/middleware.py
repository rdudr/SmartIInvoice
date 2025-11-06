import logging
import traceback
from django.http import JsonResponse
from django.shortcuts import render
from django.conf import settings

logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware:
    """
    Middleware for comprehensive error handling and logging
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_exception(self, request, exception):
        """
        Handle uncaught exceptions with proper logging and user-friendly responses
        """
        # Log the full exception with traceback
        logger.error(
            f"Unhandled exception in {request.method} {request.path}: {str(exception)}",
            extra={
                'request': request,
                'user': getattr(request, 'user', None),
                'exception_type': type(exception).__name__,
                'traceback': traceback.format_exc()
            }
        )
        
        # For AJAX requests, return JSON error response
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': 'An unexpected error occurred. Please try again.',
                'error_code': 'UNEXPECTED_ERROR'
            }, status=500)
        
        # For regular requests, render error page
        if settings.DEBUG:
            # In debug mode, let Django handle it (show detailed error)
            return None
        else:
            # In production, show user-friendly error page
            return render(request, 'errors/500.html', {
                'error_title': 'Server Error',
                'error_message': 'An unexpected error occurred. Our team has been notified.',
                'error_code': '500'
            }, status=500)


class SecurityHeadersMiddleware:
    """
    Middleware to add security headers for better error handling
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        
        # Don't cache error pages
        if response.status_code >= 400:
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        
        return response


class RequestLoggingMiddleware:
    """
    Middleware to log important requests and responses for debugging
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Log important requests
        if request.path.startswith('/upload') or request.path.startswith('/verify') or request.path.startswith('/captcha'):
            logger.info(
                f"Request: {request.method} {request.path}",
                extra={
                    'user': getattr(request, 'user', None),
                    'ip_address': self.get_client_ip(request),
                    'user_agent': request.META.get('HTTP_USER_AGENT', '')
                }
            )
        
        response = self.get_response(request)
        
        # Log error responses
        if response.status_code >= 400:
            logger.warning(
                f"Error response: {response.status_code} for {request.method} {request.path}",
                extra={
                    'user': getattr(request, 'user', None),
                    'ip_address': self.get_client_ip(request),
                    'status_code': response.status_code
                }
            )
        
        return response
    
    def get_client_ip(self, request):
        """Get the client's IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip