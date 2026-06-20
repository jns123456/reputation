"""Global platform rank helpers for profile badges and similar surfaces."""

from django.core.cache import cache

from accounts.models import UserProfile
from reputation.ranking_modes import (
    get_relative_ranking_min_scored_forecasts,
    qualifies_for_relative_ranking,
)

TOP_PLATFORM_RANK = 3

REPUTATION_ABSOLUTE = "reputation_absolute"
REPUTATION_RELATIVE = "reputation_relative"
POPULARITY = "popularity"

_BADGE_KIND_ORDER = (REPUTATION_ABSOLUTE, REPUTATION_RELATIVE, POPULARITY)


def get_user_reputation_rank_absolute(profile):
    """Return 1-based rank by total reputation points."""
    higher = UserProfile.objects.filter(reputation_points__gt=profile.reputation_points).count()
    tied_score = UserProfile.objects.filter(
        reputation_points=profile.reputation_points,
        reputation_score__gt=profile.reputation_score,
    ).count()
    tied_scored = UserProfile.objects.filter(
        reputation_points=profile.reputation_points,
        reputation_score=profile.reputation_score,
        scored_forecast_count__gt=profile.scored_forecast_count,
    ).count()
    return higher + tied_score + tied_scored + 1


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


def get_user_popularity_rank(profile):
    """Return 1-based rank by popularity score."""
    higher = UserProfile.objects.filter(popularity_score__gt=profile.popularity_score).count()
    tied = UserProfile.objects.filter(
        popularity_score=profile.popularity_score,
        popularity_points__gt=profile.popularity_points,
    ).count()
    return higher + tied + 1


def _platform_top_rank_cache_key(*, max_rank):
    return f"platform_top_rank_index:{max_rank}"


def build_platform_top_rank_index(*, max_rank=TOP_PLATFORM_RANK):
    """Build user_id -> badge list for everyone in the global top N leaderboards."""
    from dashboard.leaderboard_cache import (
        get_cached_top_popular_users,
        get_cached_top_predictors,
    )
    from reputation.leaderboard import build_leaderboard_rows
    from reputation.ranking_modes import ABSOLUTE, RELATIVE

    index = {}

    for rank, profile in enumerate(
        get_cached_top_predictors(limit=max_rank, mode=ABSOLUTE),
        start=1,
    ):
        index.setdefault(profile.user_id, []).append(
            {"kind": REPUTATION_ABSOLUTE, "rank": rank}
        )

    relative_rows = build_leaderboard_rows(
        get_cached_top_predictors(limit=50, mode=RELATIVE),
        ranking_mode=RELATIVE,
    )
    for row in relative_rows:
        if row["rank"] is None or row["rank"] > max_rank:
            continue
        user_id = row["stats"].user_id
        badges = index.setdefault(user_id, [])
        if any(badge["kind"] == REPUTATION_RELATIVE for badge in badges):
            continue
        badges.append({"kind": REPUTATION_RELATIVE, "rank": row["rank"]})

    for rank, profile in enumerate(get_cached_top_popular_users(limit=max_rank), start=1):
        index.setdefault(profile.user_id, []).append({"kind": POPULARITY, "rank": rank})

    for badges in index.values():
        badges.sort(key=lambda badge: _BADGE_KIND_ORDER.index(badge["kind"]))

    return index


def get_platform_top_rank_index(*, max_rank=TOP_PLATFORM_RANK):
    """Cached lookup table for global top-N platform rank badges."""
    from dashboard.leaderboard_cache import leaderboard_cache_seconds

    cache_key = _platform_top_rank_cache_key(max_rank=max_rank)
    index = cache.get(cache_key)
    if index is not None:
        return index

    index = build_platform_top_rank_index(max_rank=max_rank)
    cache.set(cache_key, index, leaderboard_cache_seconds())
    return index


def get_user_platform_top_rank_badges(user, *, max_rank=TOP_PLATFORM_RANK):
    """
    Return top-rank badges for a user when they place in the global top N.

    Each badge is {"kind": str, "rank": int} for reputation absolute, reputation
    relative (rep / forecast), and popularity leaderboards.
    """
    if user is None or not getattr(user, "pk", None):
        return []

    return list(get_platform_top_rank_index(max_rank=max_rank).get(user.pk, []))
