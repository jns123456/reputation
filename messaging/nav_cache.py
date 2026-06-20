"""Short-lived cache for DM badge counts."""

from django.conf import settings
from django.core.cache import cache


def dm_badge_cache_seconds() -> int:
    return getattr(settings, "NAV_BADGE_CACHE_SECONDS", 60)


def unread_dm_count_cache_key(user_id: int) -> str:
    return f"nav:unread_dm:{user_id}"


def invalidate_dm_nav_cache(user_id: int) -> None:
    cache.delete(unread_dm_count_cache_key(user_id))


def get_cached_unread_dm_count(*, user) -> int:
    if not user or not user.is_authenticated:
        return 0

    cache_key = unread_dm_count_cache_key(user.id)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from messaging.selectors import get_unread_message_count

    count = get_unread_message_count(user=user)
    cache.set(cache_key, count, dm_badge_cache_seconds())
    return count
