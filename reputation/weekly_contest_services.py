"""Weekly reputation contest — calendar-week standings and prize winners.

Standings reuse immutable ``ReputationEvent`` aggregation (``period_leaderboard``)
so weekly boards stay auditable. Prizes are display-only cash amounts — no
on-platform payments (AGENTS.md §2).
"""

from datetime import datetime, time, timedelta

from django.conf import settings
from django.utils import timezone

WEEKLY_CONTEST_ANNOUNCEMENT_SESSION_KEY = "weekly_contest_announcement"
WEEKLY_CONTEST_DISMISS_CACHE_KEY = "weekly_contest_ann_dismissed:{user_id}"


def _weekly_contest_dismiss_cache_key(user_id):
    return WEEKLY_CONTEST_DISMISS_CACHE_KEY.format(user_id=user_id)


def user_dismissed_weekly_contest_announcement(user):
    from django.core.cache import cache

    return bool(cache.get(_weekly_contest_dismiss_cache_key(user.id)))


def dismiss_weekly_contest_announcement(*, user):
    from django.core.cache import cache

    cache.set(_weekly_contest_dismiss_cache_key(user.id), True, timeout=None)


def weekly_contest_enabled():
    return bool(getattr(settings, "WEEKLY_CONTEST_ENABLED", True))


def weekly_contest_prize_usd():
    return max(1, int(getattr(settings, "WEEKLY_CONTEST_PRIZE_USD", 5)))


def get_weekly_contest_min_scored_forecasts():
    """Minimum scored forecasts in the week to qualify for either contest table."""
    return max(1, int(getattr(settings, "WEEKLY_CONTEST_MIN_SCORED_FORECASTS", 10)))


def qualifies_for_weekly_contest(scored_forecast_count):
    return int(scored_forecast_count or 0) >= get_weekly_contest_min_scored_forecasts()


def filter_weekly_contest_qualified(entries):
    return [entry for entry in entries if qualifies_for_weekly_contest(entry.scored_forecast_count)]


def pick_weekly_contest_winner(standings):
    """First qualified finisher in pre-sorted standings, or None."""
    for stats in standings:
        if qualifies_for_weekly_contest(stats.scored_forecast_count):
            return stats
    return None


def sunday_start_for_date(date):
    """Most recent Sunday on or before ``date`` (contest weeks run Sun 00:00 → Sat 23:59)."""
    days_since_sunday = (date.weekday() + 1) % 7
    return date - timedelta(days=days_since_sunday)


def week_code_for_date(date):
    """Week identifier = ISO date of the starting Sunday (``YYYY-MM-DD``)."""
    return sunday_start_for_date(date).isoformat()


def current_week_code(*, today=None):
    return week_code_for_date(today or timezone.localdate())


def week_date_range(week_code):
    """Return aware ``(since, until)`` for a contest week starting on Sunday ``YYYY-MM-DD``."""
    start_date = datetime.strptime(week_code, "%Y-%m-%d").date()
    tz = timezone.get_current_timezone()
    since = timezone.make_aware(datetime.combine(start_date, time.min), tz)
    until = since + timedelta(days=7)
    return since, until


def current_week_bounds(*, today=None):
    """Bounds for the Sun–Sat contest week containing ``today``."""
    today = today or timezone.localdate()
    start_date = sunday_start_for_date(today)
    tz = timezone.get_current_timezone()
    since = timezone.make_aware(datetime.combine(start_date, time.min), tz)
    until = since + timedelta(days=7)
    return since, until


def previous_week_code(*, today=None):
    today = today or timezone.localdate()
    return week_code_for_date(sunday_start_for_date(today) - timedelta(days=7))


def get_announcement_context():
    since, until = current_week_bounds()
    return {
        "week_code": current_week_code(),
        "week_start": since,
        "week_end": until - timedelta(seconds=1),
        "prize_usd": weekly_contest_prize_usd(),
        "min_scored": get_weekly_contest_min_scored_forecasts(),
        "contest_url_name": "dashboard:weekly_contest",
        "dismiss_url_name": "dashboard:weekly_contest_dismiss_announcement",
    }


def queue_weekly_contest_announcement(*, request):
    """Flag the next authenticated page load to show the weekly contest modal."""
    if not weekly_contest_enabled():
        return
    if not request.user.is_authenticated:
        return
    if user_dismissed_weekly_contest_announcement(request.user):
        return
    request.session[WEEKLY_CONTEST_ANNOUNCEMENT_SESSION_KEY] = True


def consume_weekly_contest_announcement(*, request):
    """Return contest announcement context once per login, if queued."""
    if not weekly_contest_enabled():
        return None
    if not request.user.is_authenticated:
        return None
    if user_dismissed_weekly_contest_announcement(request.user):
        request.session.pop(WEEKLY_CONTEST_ANNOUNCEMENT_SESSION_KEY, False)
        return None
    if not request.session.pop(WEEKLY_CONTEST_ANNOUNCEMENT_SESSION_KEY, False):
        return None
    return get_announcement_context()


def finalize_weekly_contest(week_code=None, *, prize_usd=None):
    """Record weekly winners for absolute points and rep/forecast leaders.

    Idempotent: existing winner rows are never modified or duplicated.
    Returns the number of new winner records created.
    """
    from reputation.models import WeeklyContestWinner
    from reputation.period_leaderboard import get_top_predictors_between
    from reputation.ranking_modes import ABSOLUTE, RELATIVE

    week_code = week_code or previous_week_code()
    since, until = week_date_range(week_code)
    if until > timezone.now():
        return 0

    prize_usd = prize_usd if prize_usd is not None else weekly_contest_prize_usd()
    created = 0

    for prize_type, mode in (
        (WeeklyContestWinner.PrizeType.ABSOLUTE, ABSOLUTE),
        (WeeklyContestWinner.PrizeType.RELATIVE, RELATIVE),
    ):
        standings = get_top_predictors_between(
            since=since,
            until=until,
            limit=50,
            mode=mode,
        )
        winner = pick_weekly_contest_winner(standings)
        if winner is None:
            continue

        _row, was_created = WeeklyContestWinner.objects.get_or_create(
            week_code=week_code,
            prize_type=prize_type,
            defaults={
                "user": winner.user,
                "reputation_points": winner.reputation_points,
                "reputation_score": winner.reputation_score,
                "scored_forecast_count": winner.scored_forecast_count,
                "prize_usd": prize_usd,
            },
        )
        if was_created:
            created += 1
    return created
