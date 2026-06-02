"""Reputation leaderboard ranking modes."""

from django.conf import settings

ABSOLUTE = "absolute"
RELATIVE = "relative"

REPUTATION_RANKING_MODES = (ABSOLUTE, RELATIVE)

RELATIVE_ORDERING = ("-reputation_score", "-reputation_points", "-scored_forecast_count")
ABSOLUTE_ORDERING = ("-reputation_points", "-reputation_score", "-scored_forecast_count")
UNQUALIFIED_RELATIVE_ORDERING = ("-reputation_points", "-scored_forecast_count")


def normalize_reputation_ranking_mode(mode):
    """Return a valid ranking mode; default is relative (avg per forecast)."""
    if mode == ABSOLUTE:
        return ABSOLUTE
    return RELATIVE


def get_relative_ranking_min_scored_forecasts():
    """Minimum scored forecasts; users must exceed this count to qualify for relative ranking."""
    return max(0, int(getattr(settings, "REPUTATION_RELATIVE_MIN_SCORED_FORECASTS", 10)))


def qualifies_for_relative_ranking(scored_forecast_count):
    """Return True when the user has strictly more than the minimum scored forecasts."""
    return int(scored_forecast_count or 0) > get_relative_ranking_min_scored_forecasts()
