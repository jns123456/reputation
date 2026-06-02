"""Levels and achievements — code-defined catalog + idempotent awarding.

Both systems are **popularity-flavored social proof**: they reflect activity and
milestones, and must never alter predictive reputation points (AGENTS.md §6).
Reputation levels use ``reputation_points``; popularity levels use
``popularity_points``. Achievements are durable, append-only badges.
"""

from dataclasses import dataclass
from typing import Callable

from django.utils.translation import gettext_lazy as _


# --------------------------------------------------------------------------- #
# Levels — derived from reputation_points (credibility ladder).
# --------------------------------------------------------------------------- #

# (min_points, title). Must stay sorted ascending by min_points.
REP_LEVEL_THRESHOLDS = (
    (0, _("Rookie")),
    (50, _("Apprentice")),
    (150, _("Analyst")),
    (350, _("Forecaster")),
    (700, _("Sharp")),
    (1500, _("Oracle")),
    (3000, _("Legend")),
)

# Social engagement ladder — derived from popularity_points only.
POP_LEVEL_THRESHOLDS = (
    (0, _("Newcomer")),
    (25, _("Chatter")),
    (75, _("Regular")),
    (200, _("Connector")),
    (500, _("Influencer")),
    (1000, _("Crowd Favorite")),
    (2500, _("Community Icon")),
)

# Backwards-compatible alias for imports/tests.
LEVEL_THRESHOLDS = REP_LEVEL_THRESHOLDS


def _get_level_progress(points, thresholds, *, clamp_points_at_zero=False):
    """Return level metadata for a point total and threshold table."""
    points = int(points or 0)
    if clamp_points_at_zero:
        points = max(0, points)

    level_index = 0
    for idx, (floor, _title) in enumerate(thresholds):
        if points >= floor:
            level_index = idx
        else:
            break

    floor, title = thresholds[level_index]
    is_max = level_index >= len(thresholds) - 1
    next_threshold = None if is_max else thresholds[level_index + 1][0]

    if is_max:
        progress_pct = 100
    else:
        span = next_threshold - floor
        gained = max(0, points - floor)
        progress_pct = max(0, min(100, round(gained * 100 / span))) if span else 0

    return {
        "level": level_index + 1,
        "title": title,
        "current_floor": floor,
        "next_threshold": next_threshold,
        "progress_pct": progress_pct,
        "points": points,
        "is_max": is_max,
    }


def get_level_progress(reputation_points):
    """Return reputation level metadata (credibility ladder).

    ``reputation_points`` may be negative; progress toward the next tier is
    clamped at the current floor.
    """
    return _get_level_progress(
        reputation_points,
        REP_LEVEL_THRESHOLDS,
        clamp_points_at_zero=False,
    )


def get_pop_level_progress(popularity_points):
    """Return popularity level metadata (social engagement ladder)."""
    return _get_level_progress(
        popularity_points,
        POP_LEVEL_THRESHOLDS,
        clamp_points_at_zero=True,
    )


# --------------------------------------------------------------------------- #
# Achievements — code-defined catalog, awarded idempotently.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Achievement:
    code: str
    name: object  # lazy translatable
    description: object
    icon: str  # Lucide icon name
    predicate: Callable[[dict], bool]


# ``stats`` keys provided by ``_collect_stats``:
#   prediction_count, correct_prediction_count, popularity_points,
#   reputation_points, longest_streak, challenges_won
ACHIEVEMENTS = (
    Achievement(
        "first_forecast",
        _("First Forecast"),
        _("Published your first prediction."),
        "flag",
        lambda s: s["prediction_count"] >= 1,
    ),
    Achievement(
        "forecaster_10",
        _("Getting Serious"),
        _("Published 10 predictions."),
        "target",
        lambda s: s["prediction_count"] >= 10,
    ),
    Achievement(
        "forecaster_50",
        _("Prolific Forecaster"),
        _("Published 50 predictions."),
        "crosshair",
        lambda s: s["prediction_count"] >= 50,
    ),
    Achievement(
        "first_correct",
        _("On the Board"),
        _("Got your first prediction right."),
        "check-circle",
        lambda s: s["correct_prediction_count"] >= 1,
    ),
    Achievement(
        "sharp_10",
        _("Sharp Eye"),
        _("Resolved 10 predictions correctly."),
        "eye",
        lambda s: s["correct_prediction_count"] >= 10,
    ),
    Achievement(
        "popular_100",
        _("Crowd Favorite"),
        _("Earned 100 popularity points."),
        "heart",
        lambda s: s["popularity_points"] >= 100,
    ),
    Achievement(
        "popular_500",
        _("Community Voice"),
        _("Earned 500 popularity points."),
        "megaphone",
        lambda s: s["popularity_points"] >= 500,
    ),
    Achievement(
        "streak_7",
        _("Week Warrior"),
        _("Reached a 7-day activity streak."),
        "flame",
        lambda s: s["longest_streak"] >= 7,
    ),
    Achievement(
        "streak_30",
        _("Unstoppable"),
        _("Reached a 30-day activity streak."),
        "zap",
        lambda s: s["longest_streak"] >= 30,
    ),
    Achievement(
        "challenge_win_1",
        _("First Victory"),
        _("Won your first head-to-head challenge."),
        "trophy",
        lambda s: s["challenges_won"] >= 1,
    ),
    Achievement(
        "challenge_win_5",
        _("Challenge Champ"),
        _("Won 5 head-to-head challenges."),
        "medal",
        lambda s: s["challenges_won"] >= 5,
    ),
    Achievement(
        "challenge_win_10",
        _("Duel Legend"),
        _("Won 10 head-to-head challenges."),
        "crown",
        lambda s: s["challenges_won"] >= 10,
    ),
)

ACHIEVEMENTS_BY_CODE = {a.code: a for a in ACHIEVEMENTS}


def _collect_stats(user):
    from challenges.models import Challenge

    profile = getattr(user, "profile", None)
    streak = getattr(user, "activity_streak", None)
    challenges_won = 0
    if user and getattr(user, "pk", None):
        challenges_won = Challenge.objects.filter(
            winner=user,
            status=Challenge.Status.COMPLETED,
        ).count()
    return {
        "prediction_count": getattr(profile, "prediction_count", 0) or 0,
        "correct_prediction_count": getattr(profile, "correct_prediction_count", 0) or 0,
        "popularity_points": getattr(profile, "popularity_points", 0) or 0,
        "reputation_points": getattr(profile, "reputation_points", 0) or 0,
        "longest_streak": getattr(streak, "longest_streak", 0) or 0,
        "challenges_won": challenges_won,
    }


def evaluate_achievements(user):
    """Award any newly-met achievements for ``user``. Returns list of new codes.

    Idempotent and safe to call on every engagement action — already-earned
    achievements are skipped via a unique (user, code) constraint. Never raises
    into the caller's flow.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return []

    from accounts.models import UserAchievement

    try:
        earned = set(
            UserAchievement.objects.filter(user=user).values_list("code", flat=True)
        )
        stats = _collect_stats(user)
        newly = []
        for achievement in ACHIEVEMENTS:
            if achievement.code in earned:
                continue
            if achievement.predicate(stats):
                _, created = UserAchievement.objects.get_or_create(
                    user=user,
                    code=achievement.code,
                )
                if created:
                    newly.append(achievement.code)
        return newly
    except Exception:  # pragma: no cover - gamification must never break core flows
        import logging

        logging.getLogger(__name__).warning(
            "evaluate_achievements failed for user_id=%s", getattr(user, "id", None), exc_info=True
        )
        return []


def get_user_achievements(user):
    """Return ``[(Achievement, awarded_at_or_None, unlocked_bool), ...]`` for display.

    Includes locked achievements (awarded_at=None) so the profile can show
    progress toward the full catalog.
    """
    from accounts.models import UserAchievement

    awarded = {}
    if user and getattr(user, "id", None):
        awarded = dict(
            UserAchievement.objects.filter(user=user).values_list("code", "awarded_at")
        )

    rows = []
    for achievement in ACHIEVEMENTS:
        awarded_at = awarded.get(achievement.code)
        rows.append((achievement, awarded_at, awarded_at is not None))
    return rows
