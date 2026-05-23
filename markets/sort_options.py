"""Sort options for market browse — aligned with Polymarket browse controls."""

from datetime import datetime, timezone as dt_timezone

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
    ("", "Recommended mix"),
    (SORT_TRENDING, "Trending"),
    (SORT_VOLUME, "Volume"),
    (SORT_LIQUIDITY, "Liquidity"),
    (SORT_NEWEST, "Newest"),
    (SORT_ENDING_SOON, "Ending soon"),
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


def _market_payloads(market):
    return (
        market.polymarket_raw or {},
        market.polymarket_event_raw or {},
        market.kalshi_raw or {},
    )


def market_sort_metric(market, sort: str) -> float:
    """Numeric metric from imported Polymarket/Kalshi payload for ranking."""
    keys = _METRIC_KEYS.get(sort, _METRIC_KEYS[SORT_VOLUME])
    for payload in _market_payloads(market):
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
    return market_sort_metric(market, SORT_VOLUME)


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
