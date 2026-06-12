"""Short-lived cache for navigation badge counts (avoids per-request DB hits)."""

from django.conf import settings
from django.core.cache import cache


def nav_badge_cache_seconds() -> int:
    return getattr(settings, "NAV_BADGE_CACHE_SECONDS", 60)


def unread_notification_count_cache_key(user_id: int) -> str:
    return f"nav:unread_notif:{user_id}"


def recent_notifications_cache_key(user_id: int, *, limit: int) -> str:
    return f"nav:recent_notif:{user_id}:{limit}"


def pending_challenge_invites_cache_key(user_id: int) -> str:
    return f"nav:challenge_invites:{user_id}"


def streak_cache_key(user_id: int) -> str:
    return f"nav:streak:{user_id}"


def invalidate_notification_nav_cache(user_id: int) -> None:
    cache.delete(unread_notification_count_cache_key(user_id))
    for limit in (8, 50):
        cache.delete(recent_notifications_cache_key(user_id, limit=limit))


def invalidate_streak_nav_cache(user_id: int) -> None:
    cache.delete(streak_cache_key(user_id))


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


def get_cached_recent_notifications(*, user, limit=8):
    """Recent notifications for the nav dropdown (short-lived cache)."""
    if not user or not user.is_authenticated:
        return []

    cache_key = recent_notifications_cache_key(user.id, limit=limit)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from accounts.notification_selectors import get_recent_notifications

    notifications = list(get_recent_notifications(user=user, limit=limit))
    cache.set(cache_key, notifications, nav_badge_cache_seconds())
    return notifications


def get_cached_display_streak(*, user) -> int:
    """Current streak length to show in nav (0 once it has lapsed)."""
    if not user or not user.is_authenticated:
        return 0

    cache_key = streak_cache_key(user.id)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from accounts.streak_services import get_streak

    value = get_streak(user).display_streak()
    cache.set(cache_key, value, nav_badge_cache_seconds())
    return value


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
