"""Build Forecasts feed context shared by page and HTMX partial views."""

from dashboard.forecasts_services import (
    FORECASTS_FEED_PAGE_SIZE,
    VALID_FORECAST_SORTS,
    build_forecasts_feed,
)
from predictions.selectors import get_forecasts_market_options


def _normalize_sort(sort, *, user):
    sort = (sort or "recent").strip()
    if sort not in VALID_FORECAST_SORTS:
        sort = "recent"
    if sort == "following" and not (user and user.is_authenticated):
        sort = "recent"
    if sort == "for_you" and not (user and user.is_authenticated):
        sort = "hot"
    return sort


def _parse_page(raw):
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 1


def get_forecasts_page_context(*, request, market_slug="", sort="recent", page=1):
    market_slug = (market_slug or "").strip()
    sort = _normalize_sort(sort, user=request.user)
    page = _parse_page(page)

    feed_items, has_more = build_forecasts_feed(
        user=request.user,
        market_slug=market_slug or None,
        sort=sort,
        page=page,
    )
    return {
        "feed_items": feed_items,
        "market_options": get_forecasts_market_options(),
        "active_market_slug": market_slug,
        "active_sort": sort,
        "feed_page": page,
        "feed_has_more": has_more,
        "feed_next_page": page + 1,
        "feed_page_size": FORECASTS_FEED_PAGE_SIZE,
    }
