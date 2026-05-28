"""Shared 'hot' ranking — Reddit-style time-decayed engagement score.

Used by both the Forecasts feed and the Forum feed so a single, auditable
formula governs what trends. Popularity-only signal (votes, replies); it never
touches predictive reputation (AGENTS.md §6).
"""

import math

# Epoch offset keeps the score in a readable range; arbitrary fixed constant.
_EPOCH = 1_700_000_000
# ~12.5h: how many seconds of age equal one order of magnitude of score.
_TIME_DIVISOR = 45000


def hot_score(*, points, created_at, engagement=0):
    """Rank by engagement magnitude, gently decayed toward recency.

    ``points`` = net popularity score, ``engagement`` = comments/replies.
    Older content needs disproportionately more votes to outrank fresh content.
    """
    base = (points or 0) + (engagement or 0)
    sign = 1 if base > 0 else (-1 if base < 0 else 0)
    magnitude = math.log10(max(abs(base), 1))
    seconds = created_at.timestamp() - _EPOCH
    return round(sign * magnitude + seconds / _TIME_DIVISOR, 7)
