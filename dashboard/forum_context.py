"""Build forum feed context shared by page and HTMX partial views."""

from dashboard.forum_services import build_forum_feed
from predictions.selectors import get_forum_market_options


def get_forum_page_context(*, request, market_slug=""):
    market_slug = (market_slug or "").strip()
    feed_items = build_forum_feed(
        user=request.user,
        market_slug=market_slug or None,
    )
    return {
        "feed_items": feed_items,
        "market_options": get_forum_market_options(),
        "active_market_slug": market_slug,
    }
