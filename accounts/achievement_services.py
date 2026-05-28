"""Levels and achievements — code-defined catalog + idempotent awarding.

Both systems are **popularity-flavored social proof**: they reflect activity and
milestones, and must never alter predictive reputation points (AGENTS.md §6).
Levels are derived purely from a user's reputation_points for display ordering
(a credibility ladder), while achievements are durable, append-only badges.
"""

from dataclasses import dataclass
from typing import Callable

from django.utils.translation import gettext_lazy as _lazy


# --------------------------------------------------------------------------- #
# Levels — derived from reputation_points (credibility ladder).
# --------------------------------------------------------------------------- #

# (min_points, title). Must stay sorted ascending by min_points.
LEVEL_THRESHOLDS = (
    (0, _lazy("Rookie")),
    (50, _lazy("Apprentice")),
    (150, _lazy("Analyst")),
    (350, _lazy("Forecaster")),
    (700, _lazy("Sharp")),
    (1500, _lazy("Oracle")),
    (3000, _lazy("Legend")),
)


def get_level_progress(reputation_points):
    """Return level metadata for a reputation score.

    ``reputation_points`` may be negative (bad forecasters); we clamp display
    progress to the Rookie floor. Returns a dict with: ``level`` (1-indexed),
    ``title``, ``current_floor``, ``next_threshold`` (None at max),
    ``progress_pct`` (toward next level), ``points``.
    """
    points = int(reputation_points or 0)
    level_index = 0
    for idx, (floor, _title) in enumerate(LEVEL_THRESHOLDS):
        if points >= floor:
            level_index = idx
        else:
            break

    floor, title = LEVEL_THRESHOLDS[level_index]
    is_max = level_index >= len(LEVEL_THRESHOLDS) - 1
    next_threshold = None if is_max else LEVEL_THRESHOLDS[level_index + 1][0]

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
#   reputation_points, longest_streak, follower_count
ACHIEVEMENTS = (
    Achievement(
        "first_forecast",
        _lazy("First Forecast"),
        _lazy("Published your first prediction."),
        "flag",
        lambda s: s["prediction_count"] >= 1,
    ),
    Achievement(
        "forecaster_10",
        _lazy("Getting Serious"),
        _lazy("Published 10 predictions."),
        "target",
        lambda s: s["prediction_count"] >= 10,
    ),
    Achievement(
        "forecaster_50",
        _lazy("Prolific Forecaster"),
        _lazy("Published 50 predictions."),
        "crosshair",
        lambda s: s["prediction_count"] >= 50,
    ),
    Achievement(
        "first_correct",
        _lazy("On the Board"),
        _lazy("Got your first prediction right."),
        "check-circle",
        lambda s: s["correct_prediction_count"] >= 1,
    ),
    Achievement(
        "sharp_10",
        _lazy("Sharp Eye"),
        _lazy("Resolved 10 predictions correctly."),
        "eye",
        lambda s: s["correct_prediction_count"] >= 10,
    ),
    Achievement(
        "popular_100",
        _lazy("Crowd Favorite"),
        _lazy("Earned 100 popularity points."),
        "heart",
        lambda s: s["popularity_points"] >= 100,
    ),
    Achievement(
        "popular_500",
        _lazy("Community Voice"),
        _lazy("Earned 500 popularity points."),
        "megaphone",
        lambda s: s["popularity_points"] >= 500,
    ),
    Achievement(
        "streak_7",
        _lazy("Week Warrior"),
        _lazy("Reached a 7-day activity streak."),
        "flame",
        lambda s: s["longest_streak"] >= 7,
    ),
    Achievement(
        "streak_30",
        _lazy("Unstoppable"),
        _lazy("Reached a 30-day activity streak."),
        "zap",
        lambda s: s["longest_streak"] >= 30,
    ),
)

ACHIEVEMENTS_BY_CODE = {a.code: a for a in ACHIEVEMENTS}


def _collect_stats(user):
    profile = getattr(user, "profile", None)
    streak = getattr(user, "activity_streak", None)
    return {
        "prediction_count": getattr(profile, "prediction_count", 0) or 0,
        "correct_prediction_count": getattr(profile, "correct_prediction_count", 0) or 0,
        "popularity_points": getattr(profile, "popularity_points", 0) or 0,
        "reputation_points": getattr(profile, "reputation_points", 0) or 0,
        "longest_streak": getattr(streak, "longest_streak", 0) or 0,
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
