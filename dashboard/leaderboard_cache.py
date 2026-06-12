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


def get_cached_top_predictors_for_period(
    *, period, category_slug="", limit=50, mode=None, agents_only=False
):
    from reputation.period_leaderboard import (
        PERIOD_DAYS,
        get_top_predictors_for_period,
    )
    from reputation.ranking_modes import normalize_reputation_ranking_mode

    ranking_mode = normalize_reputation_ranking_mode(mode)
    kind = f"rep:{ranking_mode}:{period}{':agents' if agents_only else ''}"
    cache_key = _cache_key(kind=kind, category_slug=category_slug, limit=limit)
    leaders = cache.get(cache_key)
    if leaders is not None:
        return leaders

    leaders = get_top_predictors_for_period(
        days=PERIOD_DAYS[period],
        limit=limit,
        mode=ranking_mode,
        category_slug=category_slug or None,
        agents_only=agents_only,
    )
    cache.set(cache_key, leaders, leaderboard_cache_seconds())
    return leaders


def get_cached_top_agent_predictors(*, limit=50, mode=None):
    """All-time leaderboard restricted to declared AI agents (Agent Arena)."""
    from accounts.models import UserProfile
    from reputation.leaderboard import fetch_ranked_entries
    from reputation.period_leaderboard import AGENT_ACCOUNT_TYPES
    from reputation.ranking_modes import normalize_reputation_ranking_mode

    ranking_mode = normalize_reputation_ranking_mode(mode)
    cache_key = _cache_key(kind=f"rep:{ranking_mode}:agents-all", category_slug="", limit=limit)
    leaders = cache.get(cache_key)
    if leaders is not None:
        return leaders

    leaders = fetch_ranked_entries(
        UserProfile.objects.select_related("user").filter(
            user__account_type__in=AGENT_ACCOUNT_TYPES
        ),
        limit=limit,
        mode=ranking_mode,
    )
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
