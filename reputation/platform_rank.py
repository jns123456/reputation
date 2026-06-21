"""Global platform rank helpers for profile badges and similar surfaces."""

from django.core.cache import cache

from accounts.models import UserProfile
from reputation.ranking_modes import (
    get_relative_ranking_min_scored_forecasts,
    qualifies_for_relative_ranking,
)

REPUTATION_RELATIVE = "reputation_relative"
RELATIVE_BADGE_RANK = 1


def get_user_reputation_rank_relative(profile):
    """Return 1-based rank among qualified relative leaders, or None if unqualified."""
    if not qualifies_for_relative_ranking(profile.scored_forecast_count):
        return None

    min_scored = get_relative_ranking_min_scored_forecasts()
    qualified = UserProfile.objects.filter(scored_forecast_count__gt=min_scored)
    higher = qualified.filter(reputation_score__gt=profile.reputation_score).count()
    tied_points = qualified.filter(
        reputation_score=profile.reputation_score,
        reputation_points__gt=profile.reputation_points,
    ).count()
    tied_scored = qualified.filter(
        reputation_score=profile.reputation_score,
        reputation_points=profile.reputation_points,
        scored_forecast_count__gt=profile.scored_forecast_count,
    ).count()
    return higher + tied_points + tied_scored + 1


def _platform_top_rank_cache_key():
    return "platform_top_rank_index:relative:1"


def build_platform_top_rank_index():
    """Build user_id -> badge list for #1 in global rep/forecast ranking."""
    from dashboard.leaderboard_cache import get_cached_top_predictors
    from reputation.leaderboard import build_leaderboard_rows
    from reputation.ranking_modes import RELATIVE

    index = {}
    relative_rows = build_leaderboard_rows(
        get_cached_top_predictors(limit=50, mode=RELATIVE),
        ranking_mode=RELATIVE,
    )
    for row in relative_rows:
        if row["rank"] != RELATIVE_BADGE_RANK:
            continue
        index[row["stats"].user_id] = [
            {"kind": REPUTATION_RELATIVE, "rank": RELATIVE_BADGE_RANK}
        ]
        break

    return index


def get_platform_top_rank_index():
    """Cached lookup table for the global #1 rep/forecast badge."""
    from dashboard.leaderboard_cache import leaderboard_cache_seconds

    cache_key = _platform_top_rank_cache_key()
    index = cache.get(cache_key)
    if index is not None:
        return index

    index = build_platform_top_rank_index()
    cache.set(cache_key, index, leaderboard_cache_seconds())
    return index


def get_user_platform_top_rank_badges(user):
    """Return the rep/forecast #1 badge for a user, or an empty list."""
    if user is None or not getattr(user, "pk", None):
        return []

    return list(get_platform_top_rank_index().get(user.pk, []))
