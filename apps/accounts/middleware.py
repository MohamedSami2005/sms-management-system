import logging
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('django')


class ActivityLoggingMiddleware(MiddlewareMixin):
    """
    Middleware that records HTTP activity for authenticated users and logs security events.
    """
    def process_response(self, request, response):
        if hasattr(request, 'user') and request.user.is_authenticated:
            # Skip static/media request logs
            path = request.path
            if not (path.startswith('/static/') or path.startswith('/media/')):
                ip_address = self.get_client_ip(request)
                logger.info(
                    f"USER_ACTIVITY | User: {request.user.username} | Role: {getattr(request.user, 'role', 'N/A')} | "
                    f"Method: {request.method} | Path: {path} | Status: {response.status_code} | IP: {ip_address}"
                )
        return response

    @staticmethod
    def get_client_ip(request) -> str:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        return ip


class LastLoginUpdateMiddleware(MiddlewareMixin):
    """
    Middleware that updates user.last_login timestamp periodically on authenticated requests.
    """
    def process_request(self, request):
        if hasattr(request, 'user') and request.user.is_authenticated:
            now = timezone.now()
            last_login = request.user.last_login
            # Update last_login if it hasn't been updated in the last 5 minutes
            if not last_login or (now - last_login).total_seconds() > 300:
                request.user.last_login = now
                request.user.save(update_fields=['last_login'])
        return None
