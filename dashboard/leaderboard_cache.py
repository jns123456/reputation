"""Short-lived cache for public leaderboard queries."""

from django.conf import settings
from django.core.cache import cache


def leaderboard_cache_seconds() -> int:
    return getattr(settings, "LEADERBOARD_CACHE_SECONDS", 120)


def _cache_key(*, kind: str, category_slug: str, limit: int) -> str:
    return f"leaderboard:{kind}:{category_slug or 'all'}:{limit}"


def get_cached_top_predictors(*, category_slug="", limit=50, mode=None):
    from accounts.category_selectors import get_top_predictors_by_category
    from accounts.selectors import get_top_predictors
    from reputation.ranking_modes import normalize_reputation_ranking_mode

    ranking_mode = normalize_reputation_ranking_mode(mode)
    cache_key = _cache_key(kind=f"rep:{ranking_mode}", category_slug=category_slug, limit=limit)
    leaders = cache.get(cache_key)
    if leaders is not None:
        return leaders

    if category_slug:
        leaders = list(get_top_predictors_by_category(category_slug, limit, mode=ranking_mode))
    else:
        leaders = list(get_top_predictors(limit, mode=ranking_mode))
    cache.set(cache_key, leaders, leaderboard_cache_seconds())
    return leaders


def get_cached_top_popular_users(*, category_slug="", limit=50):
    from accounts.category_selectors import get_top_popular_users_by_category
    from accounts.selectors import get_top_popular_users

    cache_key = _cache_key(kind="pop", category_slug=category_slug, limit=limit)
    leaders = cache.get(cache_key)
    if leaders is not None:
        return leaders

    if category_slug:
        leaders = list(get_top_popular_users_by_category(category_slug, limit))
    else:
        leaders = list(get_top_popular_users(limit))
    cache.set(cache_key, leaders, leaderboard_cache_seconds())
    return leaders
