"""
Logging utilities for the School Portal application.
Provides convenient logging functions with consistent formatting.
"""

import logging
from functools import wraps
from django.contrib.auth.models import User

# Get logger instance for this module
logger = logging.getLogger(__name__)


def log_user_action(action, user=None, details=None, level=logging.INFO):
    """
    Log a user action with standardized format.
    
    Args:
        action (str): Description of the action
        user (User): Django User object (optional)
        details (dict): Additional context information
        level (int): Logging level (default: INFO)
    """
    username = user.username if user else "Anonymous"
    user_id = user.id if user else "N/A"
    
    message = f"[USER: {username} (ID:{user_id})] {action}"
    if details:
        message += f" | Details: {details}"
    
    logger.log(level, message)


def log_security_event(event_type, user=None, ip_address=None, details=None):
    """
    Log security-related events (login attempts, permission denied, etc).
    
    Args:
        event_type (str): Type of security event
        user (User): Django User object (optional)
        ip_address (str): IP address of the request
        details (dict): Additional context
    """
    username = user.username if user else "Anonymous"
    message = f"[SECURITY: {event_type}] User: {username} | IP: {ip_address}"
    if details:
        message += f" | Details: {details}"
    
    logger.warning(message)


def log_database_operation(operation, model_name, count=1, user=None, details=None):
    """
    Log database operations (create, update, delete).
    
    Args:
        operation (str): CREATE, UPDATE, DELETE, etc.
        model_name (str): Name of the model
        count (int): Number of records affected
        user (User): User performing the operation
        details (dict): Additional context
    """
    username = user.username if user else "System"
    message = f"[DB: {operation}] {model_name} | Count: {count} | User: {username}"
    if details:
        message += f" | Details: {details}"
    
    logger.info(message)


def log_error_with_context(error_message, error_type=None, user=None, request_data=None):
    """
    Log errors with full context for debugging.
    
    Args:
        error_message (str): Error message
        error_type (str): Type of error
        user (User): User when error occurred
        request_data (dict): Request data for context
    """
    username = user.username if user else "Anonymous"
    message = f"[ERROR: {error_type or 'UNKNOWN'}] {error_message} | User: {username}"
    if request_data:
        message += f" | Request: {request_data}"
    
    logger.error(message, exc_info=True)


def view_logger(view_func):
    """
    Decorator to log view access and execution time.
    Usage: @view_logger
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        import time
        
        start_time = time.time()
        user = request.user if request.user.is_authenticated else None
        
        # Log view access
        log_user_action(
            f"Accessed view: {view_func.__name__}",
            user=user,
            details={
                "path": request.path,
                "method": request.method,
                "ip": get_client_ip(request)
            }
        )
        
        try:
            response = view_func(request, *args, **kwargs)
            execution_time = time.time() - start_time
            
            # Log successful completion
            logger.info(
                f"[VIEW: {view_func.__name__}] Completed in {execution_time:.2f}s "
                f"| Status: {response.status_code}"
            )
            return response
            
        except Exception as e:
            execution_time = time.time() - start_time
            log_error_with_context(
                str(e),
                error_type="VIEW_ERROR",
                user=user,
                request_data={
                    "view": view_func.__name__,
                    "path": request.path,
                    "method": request.method,
                    "execution_time": f"{execution_time:.2f}s"
                }
            )
            raise
    
    return wrapper


def get_client_ip(request):
    """
    Get client IP address from request, considering trusted proxies.

    When SECURE_PROXY_SSL_HEADER is set in settings, Django already
    validates that the request was forwarded by a trusted proxy. In
    that case we take the *rightmost untrusted* entry of
    X-Forwarded-For (i.e. the last IP added by the trusted hop).

    If no proxy is configured we fall back to REMOTE_ADDR and ignore
    any X-Forwarded-For header to prevent spoofing.
    """
    from django.conf import settings as _settings
    remote_addr = request.META.get('REMOTE_ADDR', '')
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if not xff:
        return remote_addr
    chain = [p.strip() for p in xff.split(',') if p.strip()]
    if not chain:
        return remote_addr
    if getattr(_settings, 'SECURE_PROXY_SSL_HEADER', None):
        # Rightmost IP = added by the trusted proxy hop = real client.
        return chain[-1]
    # No trusted proxy configured — don't trust client-supplied XFF.
    return remote_addr
