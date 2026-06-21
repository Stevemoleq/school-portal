import logging

from django.http import JsonResponse
from django.db import connection

logger = logging.getLogger(__name__)


def health_check(request):
    """Health check endpoint for monitoring and load balancers.

    Returns a boolean status only. The raw DB error message is logged
    server-side but never returned in the response, to avoid leaking
    driver errors, hostnames, or schema details to unauthenticated
    callers.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        healthy = True
    except Exception:
        logger.exception("Health check database probe failed")
        healthy = False

    return JsonResponse({
        "status": "healthy" if healthy else "unhealthy",
        "database": "ok" if healthy else "error",
    })
