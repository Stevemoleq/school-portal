"""
Logging middleware for tracking HTTP requests and responses.

Logs the request line at INFO and the response code/duration at INFO
or WARNING for errors. User identity is recorded as an opaque ID, not
a username, so log files don't leak account names to backup or
log-shipping systems that don't share the database's access controls.

Heavily-trafficked paths (static / media / health) are skipped.
"""

import logging
import time
from django.utils.deprecation import MiddlewareMixin
from apps.core.logging_utils import get_client_ip

logger = logging.getLogger(__name__)

_SKIP_PREFIXES = ('/static/', '/media/', '/health/')


def _user_id(request):
    user = getattr(request, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):
        return user.id
    return None


class RequestLoggingMiddleware(MiddlewareMixin):
    """Logs HTTP request/response with timing and a stable user id."""

    def process_request(self, request):
        request.start_time = time.time()
        if request.path.startswith(_SKIP_PREFIXES):
            return None
        logger.info(
            "[REQ] %s %s | uid=%s | ip=%s",
            request.method,
            request.path,
            _user_id(request),
            get_client_ip(request),
        )
        return None

    def process_response(self, request, response):
        if request.path.startswith(_SKIP_PREFIXES):
            return response

        if hasattr(request, 'start_time'):
            execution_time = time.time() - request.start_time
            if response.status_code >= 500:
                log_level = logging.ERROR
            elif response.status_code >= 400:
                log_level = logging.WARNING
            else:
                log_level = logging.INFO
            logger.log(
                log_level,
                "[RES] %s %s | status=%s | %.3fs | uid=%s",
                request.method,
                request.path,
                response.status_code,
                execution_time,
                _user_id(request),
            )
        return response
