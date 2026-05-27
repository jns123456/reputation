"""Sort options for market browse — aligned with Polymarket browse controls."""

from datetime import datetime, timezone as dt_timezone

from django.utils.translation import gettext_lazy as _

SORT_TRENDING = "trending"
SORT_VOLUME = "volume"
SORT_LIQUIDITY = "liquidity"
SORT_NEWEST = "newest"
SORT_ENDING_SOON = "ending_soon"

VALID_MARKET_SORTS = frozenset(
    {
        SORT_TRENDING,
        SORT_VOLUME,
        SORT_LIQUIDITY,
        SORT_NEWEST,
        SORT_ENDING_SOON,
    }
)

MARKET_SORT_CHOICES = (
    ("", _("Recommended mix")),
    (SORT_TRENDING, _("Trending")),
    (SORT_VOLUME, _("Volume")),
    (SORT_LIQUIDITY, _("Liquidity")),
    (SORT_NEWEST, _("Newest")),
    (SORT_ENDING_SOON, _("Ending soon")),
)

_METRIC_KEYS = {
    SORT_TRENDING: ("volume24hr", "volume24hrClob", "volume_24h_fp"),
    SORT_VOLUME: ("volumeNum", "volume", "volume_fp"),
    SORT_LIQUIDITY: ("liquidityNum", "liquidityClob", "liquidity"),
}


def normalize_sort_filter(value: str) -> str:
    value = (value or "").strip()
    if value in VALID_MARKET_SORTS:
        return value
    return ""


def _market_payloads(market, *, include_event_payloads=False):
    payloads = (
        market.polymarket_raw or {},
        market.kalshi_raw or {},
    )
    if include_event_payloads:
        payloads = (
            *payloads,
            market.polymarket_event_raw or {},
            market.kalshi_event_raw or {},
        )
    return payloads


def market_sort_metric(market, sort: str) -> float:
    """Numeric metric from imported Polymarket/Kalshi payload for ranking."""
    keys = _METRIC_KEYS.get(sort, _METRIC_KEYS[SORT_VOLUME])
    include_event_payloads = sort != SORT_VOLUME
    for payload in _market_payloads(market, include_event_payloads=include_event_payloads):
        for key in keys:
            value = payload.get(key)
            if value is None or value == "":
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return 0.0


def market_volume(market) -> float:
    """Total traded volume — used for default cards and source blending."""
    from markets.display_metadata import market_volume_for_sort

    return market_volume_for_sort(market)


def sort_markets(markets, *, sort: str):
    sort = normalize_sort_filter(sort)
    if not sort:
        return markets

    if sort == SORT_NEWEST:
        return sorted(markets, key=lambda market: (market.created_at, market.updated_at), reverse=True)

    if sort == SORT_ENDING_SOON:
        far_future = datetime.max.replace(tzinfo=dt_timezone.utc)
        return sorted(
            markets,
            key=lambda market: (
                market.close_date or far_future,
                -market_volume(market),
            ),
        )

    return sorted(
        markets,
        key=lambda market: (market_sort_metric(market, sort), market.updated_at),
        reverse=True,
    )
