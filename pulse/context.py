"""Build Forum page context shared by page and HTMX partial views."""

from pulse.selectors import build_pulse_feed


def get_forum_page_context(*, request, limit=50):
    return {
        "feed_items": build_pulse_feed(user=request.user, limit=limit),
    }
