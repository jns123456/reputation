"""Short-lived cache for navigation badge counts (avoids per-request DB hits)."""

from django.conf import settings
from django.core.cache import cache


def nav_badge_cache_seconds() -> int:
    return getattr(settings, "NAV_BADGE_CACHE_SECONDS", 60)


def unread_notification_count_cache_key(user_id: int) -> str:
    return f"nav:unread_notif:{user_id}"


def pending_challenge_invites_cache_key(user_id: int) -> str:
    return f"nav:challenge_invites:{user_id}"


def invalidate_notification_nav_cache(user_id: int) -> None:
    cache.delete(unread_notification_count_cache_key(user_id))


def invalidate_challenge_nav_cache(user_id: int) -> None:
    cache.delete(pending_challenge_invites_cache_key(user_id))


def get_cached_unread_notification_count(*, user) -> int:
    if not user or not user.is_authenticated:
        return 0

    cache_key = unread_notification_count_cache_key(user.id)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from accounts.notification_services import get_unread_notification_count

    count = get_unread_notification_count(user=user)
    cache.set(cache_key, count, nav_badge_cache_seconds())
    return count


def get_cached_pending_challenge_invites_count(*, user) -> int:
    if not user or not user.is_authenticated:
        return 0

    cache_key = pending_challenge_invites_cache_key(user.id)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from challenges.models import Challenge, ChallengeParticipant

    count = ChallengeParticipant.objects.filter(
        user=user,
        status=ChallengeParticipant.Status.INVITED,
        challenge__status=Challenge.Status.PENDING,
    ).count()
    cache.set(cache_key, count, nav_badge_cache_seconds())
    return count
