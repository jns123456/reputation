"""Reputation leaderboard ranking modes."""

ABSOLUTE = "absolute"
RELATIVE = "relative"

REPUTATION_RANKING_MODES = (ABSOLUTE, RELATIVE)


def normalize_reputation_ranking_mode(mode):
    """Return a valid ranking mode; default is relative (avg per forecast)."""
    if mode == ABSOLUTE:
        return ABSOLUTE
    return RELATIVE
