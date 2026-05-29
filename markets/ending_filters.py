"""Time-window ("ending soon") filter for market browse.

Lets users surface markets whose ``close_date`` is imminent — e.g. all events
ending within the next 24 hours. Kept separate from sort options because this
restricts the result set rather than just reordering it.
"""

from django.utils.translation import gettext_lazy as _

ENDING_24H = "24h"
ENDING_48H = "48h"
ENDING_72H = "72h"
ENDING_7D = "7d"

# Default window for the "Ending soon" entry point.
DEFAULT_ENDING_WINDOW = ENDING_24H

ENDING_WINDOW_HOURS = {
    ENDING_24H: 24,
    ENDING_48H: 48,
    ENDING_72H: 72,
    ENDING_7D: 168,
}

ENDING_WINDOW_CHOICES = (
    (ENDING_24H, _("Next 24h")),
    (ENDING_48H, _("Next 48h")),
    (ENDING_72H, _("Next 72h")),
    (ENDING_7D, _("Next week")),
)


def normalize_ending_filter(value: str) -> str:
    """Return a valid ending-window key, or empty string when not applicable."""
    value = (value or "").strip()
    if value in ENDING_WINDOW_HOURS:
        return value
    return ""


def ending_window_hours(value: str):
    """Hours for a window key, or None when the filter is inactive/invalid."""
    return ENDING_WINDOW_HOURS.get(normalize_ending_filter(value))
