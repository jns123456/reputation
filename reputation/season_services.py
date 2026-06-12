"""Quarterly reputation seasons — permanent awards for top finishers.

Season standings are computed from immutable ``ReputationEvent`` records, so
finalization is auditable and idempotent. Awards are popularity-flavored
social proof (profile badges) and never change scoring (AGENTS.md §6).
"""

import logging
from datetime import datetime, timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

SEASON_TOP_N = 10
# Only finishers with a real sample earn a permanent badge.
SEASON_MIN_SCORED_FORECASTS = 5


def season_code_for_date(date):
    quarter = (date.month - 1) // 3 + 1
    return f"{date.year}-Q{quarter}"


def previous_season_code(*, today=None):
    today = today or timezone.localdate()
    first_of_quarter = today.replace(month=((today.month - 1) // 3) * 3 + 1, day=1)
    last_quarter_day = first_of_quarter - timedelta(days=1)
    return season_code_for_date(last_quarter_day)


def season_date_range(season_code):
    """Return aware ``(start, end)`` datetimes for a ``YYYY-QN`` code."""
    year_str, quarter_str = season_code.split("-Q")
    year = int(year_str)
    quarter = int(quarter_str)
    start_month = (quarter - 1) * 3 + 1
    tz = timezone.get_current_timezone()
    start = datetime(year, start_month, 1, tzinfo=tz)
    if quarter == 4:
        end = datetime(year + 1, 1, 1, tzinfo=tz)
    else:
        end = datetime(year, start_month + 3, 1, tzinfo=tz)
    return start, end


def finalize_season(season_code=None, *, top_n=SEASON_TOP_N):
    """Create permanent ``SeasonAward`` rows for the season's top finishers.

    Idempotent: existing awards are never modified or duplicated. Returns the
    number of awards created.
    """
    from reputation.models import SeasonAward
    from reputation.period_leaderboard import get_top_predictors_between
    from reputation.ranking_modes import RELATIVE

    season_code = season_code or previous_season_code()
    since, until = season_date_range(season_code)
    if until > timezone.now():
        logger.info("Season %s has not ended yet; skipping finalization.", season_code)
        return 0

    standings = get_top_predictors_between(
        since=since,
        until=until,
        limit=top_n * 2,
        mode=RELATIVE,
    )

    created = 0
    rank = 0
    for stats in standings:
        if stats.scored_forecast_count < SEASON_MIN_SCORED_FORECASTS:
            continue
        rank += 1
        if rank > top_n:
            break
        _award, was_created = SeasonAward.objects.get_or_create(
            user=stats.user,
            season=season_code,
            category_slug="",
            defaults={
                "rank": rank,
                "reputation_points": stats.reputation_points,
                "reputation_score": stats.reputation_score,
                "scored_forecast_count": stats.scored_forecast_count,
            },
        )
        if was_created:
            created += 1
    return created


def get_user_season_awards(user, *, limit=8):
    from reputation.models import SeasonAward

    return list(
        SeasonAward.objects.filter(user=user).order_by("-season", "rank")[:limit]
    )
