"""Denormalized card/sort metadata extracted from imported market payloads."""

from __future__ import annotations

from markets.sort_options import SORT_LIQUIDITY, SORT_VOLUME, market_sort_metric


def format_volume_label(amount: float) -> str:
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.1f}M Vol."
    if amount >= 1_000:
        return f"${amount / 1_000:.0f}K Vol."
    if amount > 0:
        return f"${amount:.0f} Vol."
    return ""


def extract_volume_total_from_market(market) -> float:
    return market_sort_metric(market, SORT_VOLUME)


def extract_volume_24h_from_market(market) -> float:
    return market_sort_metric(market, "trending")


def extract_liquidity_total_from_market(market) -> float:
    return market_sort_metric(market, SORT_LIQUIDITY)


def extract_card_image_url_from_market(market) -> str:
    raw = market.polymarket_raw or {}
    event = market.polymarket_event_raw or {}
    event_data = event.get("event") if isinstance(event, dict) else {}
    if not isinstance(event_data, dict):
        event_data = event if isinstance(event, dict) else {}
    return (
        raw.get("image")
        or raw.get("icon")
        or raw.get("image_url")
        or event.get("image")
        or event.get("icon")
        or event_data.get("image")
        or event_data.get("icon")
        or ""
    )


def sync_market_display_metadata(market, *, save: bool = False) -> None:
    """Refresh denormalized card/sort fields from the market's import payloads."""
    market.volume_total = extract_volume_total_from_market(market)
    market.volume_24h = extract_volume_24h_from_market(market)
    market.liquidity_total = extract_liquidity_total_from_market(market)
    market.card_image_url = extract_card_image_url_from_market(market)
    if save:
        market.save(
            update_fields=[
                "volume_total",
                "volume_24h",
                "liquidity_total",
                "card_image_url",
                "updated_at",
            ]
        )


def market_volume_for_sort(market) -> float:
    """Volume for ranking — prefers denormalized DB field when present."""
    stored = getattr(market, "volume_total", None)
    if stored is not None and stored > 0:
        return float(stored)
    # On card/list querysets the raw payloads are deferred; reading them here
    # would trigger a per-row DB fetch (N+1). The denormalized column is
    # authoritative there, so fall back to it instead of the payload.
    deferred = getattr(market, "_card_payloads_deferred", None)
    if callable(deferred) and deferred():
        return float(stored or 0.0)
    return extract_volume_total_from_market(market)


def market_liquidity_for_sort(market) -> float:
    """Liquidity for ranking — prefers denormalized DB field when present."""
    stored = getattr(market, "liquidity_total", None)
    if stored is not None and stored > 0:
        return float(stored)
    deferred = getattr(market, "_card_payloads_deferred", None)
    if callable(deferred) and deferred():
        return float(stored or 0.0)
    return extract_liquidity_total_from_market(market)
