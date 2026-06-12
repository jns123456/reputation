"""Time-window (e.g. 30-day) reputation leaderboards.

Rows are aggregated from immutable ``ReputationEvent`` records inside the
window, so period boards stay fully auditable and never require new
denormalized counters. Results are small (top N) and cached by the caller
(``dashboard.leaderboard_cache``); never compute these per request without
the cache layer.
"""

from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Q, Sum
from django.utils import timezone

from reputation.models import ReputationEvent
from reputation.ranking_modes import (
    ABSOLUTE,
    normalize_reputation_ranking_mode,
    qualifies_for_relative_ranking,
)

PERIOD_ALL = "all"
PERIOD_30D = "30d"
VALID_LEADERBOARD_PERIODS = (PERIOD_ALL, PERIOD_30D)
PERIOD_DAYS = {PERIOD_30D: 30}

AGENT_ACCOUNT_TYPES = ("declared_agent", "organization_agent")


def normalize_leaderboard_period(period):
    if period in VALID_LEADERBOARD_PERIODS:
        return period
    return PERIOD_ALL


@dataclass
class PeriodLeaderboardStats:
    """Duck-typed leaderboard row compatible with the reputation row partial."""

    user: object
    reputation_points: int
    reputation_score: float
    scored_forecast_count: int
    prediction_count: int
    correct_prediction_count: int
    incorrect_prediction_count: int


def get_top_predictors_for_period(
    *,
    days=30,
    limit=50,
    mode=None,
    category_slug=None,
    agents_only=False,
):
    """Top predictors by reputation earned inside the trailing window."""
    since = timezone.now() - timedelta(days=days)
    return get_top_predictors_between(
        since=since,
        until=None,
        limit=limit,
        mode=mode,
        category_slug=category_slug,
        agents_only=agents_only,
    )


def get_top_predictors_between(
    *,
    since,
    until=None,
    limit=50,
    mode=None,
    category_slug=None,
    agents_only=False,
):
    """Top predictors by reputation earned inside an explicit window."""
    ranking_mode = normalize_reputation_ranking_mode(mode)

    qs = ReputationEvent.objects.filter(created_at__gte=since)
    if until is not None:
        qs = qs.filter(created_at__lt=until)
    if category_slug:
        qs = qs.filter(prediction__market__canonical_category_slug=category_slug)
    if agents_only:
        qs = qs.filter(user__account_type__in=AGENT_ACCOUNT_TYPES)

    aggregated = (
        qs.values("user_id")
        .annotate(
            points=Sum("points_delta"),
            scored=Count("prediction", distinct=True),
            correct=Count(
                "prediction",
                distinct=True,
                filter=Q(event_type=ReputationEvent.EventType.CORRECT_PREDICTION),
            ),
            incorrect=Count(
                "prediction",
                distinct=True,
                filter=Q(event_type=ReputationEvent.EventType.INCORRECT_PREDICTION),
            ),
        )
        .order_by("-points")[: limit * 3]
    )
    rows = list(aggregated)
    if not rows:
        return []

    from django.contrib.auth import get_user_model

    User = get_user_model()
    users_by_id = {
        user.id: user
        for user in User.objects.filter(id__in=[row["user_id"] for row in rows]).select_related(
            "profile"
        )
    }

    min_sample = max(1, int(getattr(settings, "REPUTATION_SCORE_MIN_SAMPLE", 3)))
    stats = []
    for row in rows:
        user = users_by_id.get(row["user_id"])
        if user is None:
            continue
        points = row["points"] or 0
        scored = row["scored"] or 0
        stats.append(
            PeriodLeaderboardStats(
                user=user,
                reputation_points=points,
                reputation_score=round(points / max(scored, min_sample), 2),
                scored_forecast_count=scored,
                prediction_count=scored,
                correct_prediction_count=row["correct"] or 0,
                incorrect_prediction_count=row["incorrect"] or 0,
            )
        )

    if ranking_mode == ABSOLUTE:
        stats.sort(key=lambda s: (s.reputation_points, s.reputation_score), reverse=True)
        return stats[:limit]

    qualified = [s for s in stats if qualifies_for_relative_ranking(s.scored_forecast_count)]
    unqualified = [s for s in stats if not qualifies_for_relative_ranking(s.scored_forecast_count)]
    qualified.sort(
        key=lambda s: (s.reputation_score, s.reputation_points, s.scored_forecast_count),
        reverse=True,
    )
    unqualified.sort(
        key=lambda s: (s.reputation_points, s.scored_forecast_count),
        reverse=True,
    )
    return (qualified + unqualified)[:limit]
