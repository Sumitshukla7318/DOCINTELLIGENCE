import redis
from django.conf import settings
from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """
    GET /api/health/

    Checks all critical dependencies:
    - Database (PostgreSQL)
    - Cache/Broker (Redis)

    Used by Railway to verify the app is running.
    Returns 200 if healthy, 503 if any dependency is down.
    """
    health = {
        "status": "healthy",
        "database": "ok",
        "redis": "ok",
    }
    status_code = 200

    # Check database
    try:
        connection.ensure_connection()
    except Exception as exc:
        health["database"] = f"error: {str(exc)}"
        health["status"] = "unhealthy"
        status_code = 503

    # Check Redis
    try:
        r = redis.from_url(settings.CELERY_BROKER_URL)
        r.ping()
    except Exception as exc:
        health["redis"] = f"error: {str(exc)}"
        health["status"] = "unhealthy"
        status_code = 503

    return Response(health, status=status_code)