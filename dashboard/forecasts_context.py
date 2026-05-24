"""Build Forecasts feed context shared by page and HTMX partial views."""

from dashboard.forecasts_services import build_forecasts_feed
from predictions.selectors import get_forecasts_market_options


def get_forecasts_page_context(*, request, market_slug=""):
    market_slug = (market_slug or "").strip()
    feed_items = build_forecasts_feed(
        user=request.user,
        market_slug=market_slug or None,
    )
    return {
        "feed_items": feed_items,
        "market_options": get_forecasts_market_options(),
        "active_market_slug": market_slug,
    }
