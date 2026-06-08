"""Activity streak tracking — the daily-habit retention loop.

A streak counts consecutive calendar days on which a user takes at least one
engagement action (forecast, comment, vote, forum post). Streaks reward the
POPULARITY dimension only; predictive reputation still comes solely from
resolved predictions (AGENTS.md §6).
"""

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

# Streak length -> one-time popularity bonus awarded on reaching it.
STREAK_MILESTONES = {7: 5, 30: 25, 100: 100, 365: 500}

# Minimum streak length before we bother someone with a "don't lose it" reminder.
STREAK_RISK_MIN_DAYS = 2


def get_streak(user):
    from accounts.models import ActivityStreak

    streak, _ = ActivityStreak.objects.get_or_create(user=user)
    return streak


def record_activity(user, *, when=None):
    """Register an engagement action and update the user's streak.

    Idempotent per day: extra actions on the same day keep the streak value.
    Safe to call inside or outside an existing transaction. Never raises — a
    streak hiccup must not break the underlying action.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return None

    today = when or timezone.localdate()

    try:
        with transaction.atomic():
            streak = _record_activity_locked(user=user, today=today)
    except Exception:  # pragma: no cover - defensive: streak must never break an action
        logger.warning("record_activity failed for user_id=%s", getattr(user, "id", None), exc_info=True)
        return None

    # Re-check achievement milestones on every engagement action. Runs outside
    # the streak lock and never raises into the caller (AGENTS.md §6: badges are
    # popularity-flavored and must not touch reputation).
    from accounts.achievement_services import evaluate_achievements

    evaluate_achievements(user)
    return streak


def _record_activity_locked(*, user, today):
    from accounts.models import ActivityStreak

    streak = ActivityStreak.objects.select_for_update().filter(user=user).first()
    if streak is None:
        streak = ActivityStreak.objects.create(
            user=user,
            current_streak=1,
            longest_streak=1,
            last_active_date=today,
        )
        _invalidate_nav_cache(user.id)
        _maybe_award_milestone(streak)
        return streak

    if streak.last_active_date == today:
        return streak

    if streak.last_active_date == today - timedelta(days=1):
        streak.current_streak += 1
    else:
        streak.current_streak = 1

    streak.last_active_date = today
    if streak.current_streak > streak.longest_streak:
        streak.longest_streak = streak.current_streak

    update_fields = [
        "current_streak",
        "longest_streak",
        "last_active_date",
        "updated_at",
    ]
    if streak.current_streak % 7 == 0:
        streak.streak_7_completions += 1
        update_fields.append("streak_7_completions")
    if streak.current_streak % 30 == 0:
        streak.streak_30_completions += 1
        update_fields.append("streak_30_completions")

    streak.save(update_fields=update_fields)
    _invalidate_nav_cache(user.id)
    _maybe_award_milestone(streak)
    return streak


def _invalidate_nav_cache(user_id):
    try:
        from accounts.nav_cache import invalidate_streak_nav_cache

        invalidate_streak_nav_cache(user_id)
    except Exception:  # pragma: no cover - cache backend should always be present
        pass


def _maybe_award_milestone(streak):
    bonus = STREAK_MILESTONES.get(streak.current_streak)
    if not bonus:
        return
    from reputation.models import PopularityEvent
    from reputation.popularity_services import record_popularity_event

    record_popularity_event(
        user=streak.user,
        points_delta=bonus,
        event_type=PopularityEvent.EventType.STREAK_MILESTONE,
        reason=f"{streak.current_streak}-day activity streak",
    )


def get_streaks_at_risk(*, today=None):
    """Streaks alive yesterday but not yet extended today, not already reminded.

    Returns a queryset of ActivityStreak ready for an external reminder
    (email/push). In-app alerts are useless here because the user is, by
    definition, not currently on the platform.
    """
    from accounts.models import ActivityStreak

    today = today or timezone.localdate()
    yesterday = today - timedelta(days=1)
    return (
        ActivityStreak.objects.filter(
            last_active_date=yesterday,
            current_streak__gte=STREAK_RISK_MIN_DAYS,
        )
        .exclude(risk_notified_date=today)
        .select_related("user")
    )


def mark_risk_notified(streak, *, today=None):
    today = today or timezone.localdate()
    streak.risk_notified_date = today
    streak.save(update_fields=["risk_notified_date", "updated_at"])
