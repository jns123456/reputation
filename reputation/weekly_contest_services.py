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


def _parse_contest_week_start(raw):
    if hasattr(raw, "year"):
        start = raw
    else:
        start = datetime.strptime(str(raw), "%Y-%m-%d").date()
    return sunday_start_for_date(start)


def get_first_contest_week_start():
    """First Sunday when the weekly contest counts reputation (launch date)."""
    raw = getattr(settings, "WEEKLY_CONTEST_FIRST_WEEK_START", "2026-06-21")
    return _parse_contest_week_start(raw)


def get_last_contest_week_start():
    """Last Sunday that still awards weekly prizes, or None if open-ended."""
    raw = getattr(settings, "WEEKLY_CONTEST_LAST_WEEK_START", "") or ""
    if hasattr(raw, "year"):
        return sunday_start_for_date(raw)
    text = str(raw).strip()
    if not text:
        return None
    last = _parse_contest_week_start(text)
    first = get_first_contest_week_start()
    if last < first:
        return first
    return last


def contest_program_has_ended(*, today=None):
    """True once the final Sat 23:59 contest window has fully elapsed."""
    last = get_last_contest_week_start()
    if last is None:
        return False
    today = today or timezone.localdate()
    _, until = week_date_range(last.isoformat())
    end = (timezone.localtime(until) - timedelta(seconds=1)).date()
    return today > end


def normalize_contest_week_code(week_code):
    """Clamp requested weeks to the configured contest Sunday window."""
    first = get_first_contest_week_start()
    start_date = datetime.strptime(week_code, "%Y-%m-%d").date()
    if start_date < first:
        return first.isoformat()
    last = get_last_contest_week_start()
    if last is not None and start_date > last:
        return last.isoformat()
    return week_code


def current_week_code(*, today=None):
    """Active contest week — clamped to first/last configured Sundays."""
    today = today or timezone.localdate()
    first = get_first_contest_week_start()
    last = get_last_contest_week_start()
    if today < first:
        return first.isoformat()
    natural = sunday_start_for_date(today)
    if natural < first:
        return first.isoformat()
    if last is not None and natural > last:
        return last.isoformat()
    return natural.isoformat()


def is_live_contest_week(*, today=None, week_code=None):
    today = today or timezone.localdate()
    week_code = normalize_contest_week_code(week_code or current_week_code(today=today))
    since, until = week_date_range(week_code)
    start = timezone.localtime(since).date()
    end = (timezone.localtime(until) - timedelta(seconds=1)).date()
    last = get_last_contest_week_start()
    if last is not None and start > last:
        return False
    return start >= get_first_contest_week_start() and start <= today <= end


def is_upcoming_contest_week(*, today=None, week_code=None):
    today = today or timezone.localdate()
    week_code = normalize_contest_week_code(week_code or current_week_code(today=today))
    since, _until = week_date_range(week_code)
    start = timezone.localtime(since).date()
    last = get_last_contest_week_start()
    if last is not None and start > last:
        return False
    return today < start


def week_date_range(week_code):
    """Return aware ``(since, until)`` for a contest week starting on Sunday ``YYYY-MM-DD``."""
    start_date = datetime.strptime(week_code, "%Y-%m-%d").date()
    tz = timezone.get_current_timezone()
    since = timezone.make_aware(datetime.combine(start_date, time.min), tz)
    until = since + timedelta(days=7)
    return since, until


def get_user_reputation_events_for_week(*, user, week_code):
    """Reputation events that contributed to a user's weekly contest points."""
    from reputation.models import ReputationEvent

    week_code = normalize_contest_week_code(week_code)
    since, until = week_date_range(week_code)
    return (
        ReputationEvent.objects.filter(
            user=user,
            created_at__gte=since,
            created_at__lt=until,
        )
        .select_related("prediction", "prediction__market")
        .order_by("-created_at", "-id")
    )


def current_week_bounds(*, today=None):
    """Bounds for the active Sun–Sat contest week (respects launch/end dates)."""
    week_code = current_week_code(today=today)
    return week_date_range(week_code)


def previous_week_code(*, today=None):
    today = today or timezone.localdate()
    current_start = datetime.strptime(current_week_code(today=today), "%Y-%m-%d").date()
    # After the program ends, still finalize the last completed week once.
    if contest_program_has_ended(today=today):
        last = get_last_contest_week_start()
        return last.isoformat() if last is not None else None
    prev = current_start - timedelta(days=7)
    first = get_first_contest_week_start()
    if prev < first:
        return None
    return prev.isoformat()


def is_completed_contest_week(*, week_code):
    """True once the Sun–Sat contest window has fully ended."""
    _, until = week_date_range(week_code)
    return until <= timezone.now()


def list_contest_week_codes(*, today=None):
    """Contest weeks from launch through the active (or last) week (newest first)."""
    today = today or timezone.localdate()
    first = get_first_contest_week_start()
    current_start = datetime.strptime(current_week_code(today=today), "%Y-%m-%d").date()
    weeks = []
    cursor = current_start
    while cursor >= first:
        weeks.append(cursor.isoformat())
        cursor -= timedelta(days=7)
    return weeks


def build_contest_week_nav(*, selected_week_code, today=None):
    """Navigation metadata for the week picker on the contest page."""
    today = today or timezone.localdate()
    selected_week_code = normalize_contest_week_code(selected_week_code)
    nav = []
    for week_code in list_contest_week_codes(today=today):
        since, until = week_date_range(week_code)
        nav.append(
            {
                "week_code": week_code,
                "week_start": since,
                "week_end": until - timedelta(seconds=1),
                "is_current": week_code == current_week_code(today=today),
                "is_selected": week_code == selected_week_code,
                "is_completed": is_completed_contest_week(week_code=week_code),
            }
        )
    return nav


def get_weekly_contest_winners_for_week(week_code):
    """Return ``{prize_type: WeeklyContestWinner}`` for a finalized week."""
    from reputation.models import WeeklyContestWinner

    wins = WeeklyContestWinner.objects.filter(week_code=week_code).select_related("user")
    return {win.prize_type: win for win in wins}


def get_past_weekly_contest_winners(*, limit=20):
    """Historical winners grouped by week (newest first)."""
    from reputation.models import WeeklyContestWinner

    week_codes = list(
        WeeklyContestWinner.objects.values_list("week_code", flat=True)
        .distinct()
        .order_by("-week_code")[:limit]
    )
    if not week_codes:
        return []

    wins_by_week = {week_code: {} for week_code in week_codes}
    for win in WeeklyContestWinner.objects.filter(week_code__in=week_codes).select_related(
        "user"
    ):
        wins_by_week[win.week_code][win.prize_type] = win

    history = []
    for week_code in week_codes:
        since, until = week_date_range(week_code)
        history.append(
            {
                "week_code": week_code,
                "week_start": since,
                "week_end": until - timedelta(seconds=1),
                "winners": wins_by_week[week_code],
            }
        )
    return history


def get_announcement_context():
    since, until = current_week_bounds()
    week_code = current_week_code()
    return {
        "week_code": week_code,
        "week_start": since,
        "week_end": until - timedelta(seconds=1),
        "prize_usd": weekly_contest_prize_usd(),
        "min_scored": get_weekly_contest_min_scored_forecasts(),
        "is_live": is_live_contest_week(week_code=week_code),
        "is_upcoming": is_upcoming_contest_week(week_code=week_code),
        "contest_ended": contest_program_has_ended(),
        "contest_url_name": "dashboard:weekly_contest",
        "dismiss_url_name": "dashboard:weekly_contest_dismiss_announcement",
    }


def queue_weekly_contest_announcement(*, request):
    """Flag the next authenticated page load to show the weekly contest modal."""
    if not weekly_contest_enabled():
        return
    if contest_program_has_ended():
        return
    if not request.user.is_authenticated:
        return
    from reputation.weekly_contest_winner_notifications import (
        WEEKLY_CONTEST_WIN_SESSION_KEY,
        user_has_pending_weekly_contest_win,
    )

    if user_has_pending_weekly_contest_win(request.user):
        return
    if request.session.get(WEEKLY_CONTEST_WIN_SESSION_KEY):
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
    if not week_code:
        return 0
    since, until = week_date_range(week_code)
    start = timezone.localtime(since).date()
    if start < get_first_contest_week_start():
        return 0
    last = get_last_contest_week_start()
    if last is not None and start > last:
        return 0
    if until > timezone.now():
        return 0

    prize_usd = prize_usd if prize_usd is not None else weekly_contest_prize_usd()
    created = 0
    new_wins = []

    for prize_type, mode in (
        (WeeklyContestWinner.PrizeType.ABSOLUTE, ABSOLUTE),
        (WeeklyContestWinner.PrizeType.RELATIVE, RELATIVE),
    ):
        standings = get_top_predictors_between(
            since=since,
            until=until,
            limit=50,
            mode=mode,
            relative_qualifies_fn=(
                qualifies_for_weekly_contest if mode == RELATIVE else None
            ),
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
            new_wins.append(_row)

    if new_wins:
        from reputation.weekly_contest_winner_notifications import notify_weekly_contest_winners

        notify_weekly_contest_winners(new_wins)
    return created
