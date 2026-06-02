"""Leaderboard fetch and display helpers for reputation ranking modes."""

from reputation.ranking_modes import (
    ABSOLUTE,
    ABSOLUTE_ORDERING,
    RELATIVE,
    RELATIVE_ORDERING,
    UNQUALIFIED_RELATIVE_ORDERING,
    get_relative_ranking_min_scored_forecasts,
    normalize_reputation_ranking_mode,
    qualifies_for_relative_ranking,
)


def fetch_ranked_entries(queryset, *, limit, mode):
    """Return leaderboard rows ordered for the given ranking mode."""
    ranking_mode = normalize_reputation_ranking_mode(mode)
    if ranking_mode == ABSOLUTE:
        return list(queryset.order_by(*ABSOLUTE_ORDERING)[:limit])

    min_scored = get_relative_ranking_min_scored_forecasts()
    qualified = list(
        queryset.filter(scored_forecast_count__gt=min_scored).order_by(*RELATIVE_ORDERING)[:limit]
    )
    remaining = limit - len(qualified)
    if remaining <= 0:
        return qualified
    unqualified = list(
        queryset.filter(scored_forecast_count__lte=min_scored).order_by(
            *UNQUALIFIED_RELATIVE_ORDERING
        )[:remaining]
    )
    return qualified + unqualified


def build_leaderboard_rows(entries, *, ranking_mode):
    """Attach display rank and relative-qualification flags to leaderboard entries."""
    ranking_mode = normalize_reputation_ranking_mode(ranking_mode)
    rows = []
    qualified_rank = 0
    for entry in entries:
        qualifies = ranking_mode != RELATIVE or qualifies_for_relative_ranking(
            entry.scored_forecast_count
        )
        if qualifies:
            qualified_rank += 1
            rank = qualified_rank
        else:
            rank = None
        rows.append(
            {
                "stats": entry,
                "rank": rank,
                "qualifies_relative": qualifies,
            }
        )
    return rows
