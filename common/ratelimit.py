import logging
from datetime import timedelta
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


def get_daily_upload_count(user) -> int:
    """
    Counts how many documents a user has uploaded today (UTC).
    We query the DB directly — no extra dependencies needed.
    """
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    from apps.documents.models import Document
    return Document.objects.filter(
        owner=user,
        created_at__gte=today_start,
    ).count()


def check_daily_upload_limit(user) -> tuple[bool, int, int]:
    """
    Checks if a user has exceeded their daily upload limit.

    Returns:
        (is_allowed, current_count, limit)

    Each user has their own limit stored on the User model
    (set in Phase 1 as daily_upload_limit field).
    This lets admins give power users a higher limit.
    """
    limit = user.daily_upload_limit  # Per-user limit from User model
    current_count = get_daily_upload_count(user)
    is_allowed = current_count < limit
    return is_allowed, current_count, limit


def get_ratelimit_key(group: str, request) -> str:
    """
    Generates a rate limit cache key scoped to the authenticated user.
    Using user ID (not IP) means VPN/proxy changes don't reset limits.
    """
    return f"ratelimit:{group}:user:{request.user.id}"