"""Kalshi public URLs for imported markets."""

KALSHI_BASE = "https://kalshi.com/markets"


def get_kalshi_series_ticker(market):
    raw = market.kalshi_raw or {}
    event_payload = market.kalshi_event_raw or {}
    event = event_payload.get("event") if isinstance(event_payload, dict) else {}
    if not isinstance(event, dict):
        event = event_payload if isinstance(event_payload, dict) else {}
    event_ticker = raw.get("event_ticker") or ""
    return (raw.get("series_ticker") or event.get("series_ticker") or event_ticker.split("-")[0] or "").upper()


def resolve_kalshi_public_url(market):
    """Best URL for viewing this market on kalshi.com."""
    series_ticker = get_kalshi_series_ticker(market)
    if series_ticker:
        return f"{KALSHI_BASE}/{series_ticker.lower()}"
    ticker = market.kalshi_ticker or (market.kalshi_raw or {}).get("ticker") or market.external_id
    if ticker:
        return f"{KALSHI_BASE}/{ticker.lower()}"
    return ""


def resolve_kalshi_market_url(market):
    """Deep link to the Kalshi event/market page when available."""
    raw = market.kalshi_raw or {}
    event_ticker = raw.get("event_ticker") or ""
    series_ticker = get_kalshi_series_ticker(market)
    if series_ticker and event_ticker:
        return f"{KALSHI_BASE}/{series_ticker.lower()}/{event_ticker.lower()}"
    return resolve_kalshi_public_url(market)
