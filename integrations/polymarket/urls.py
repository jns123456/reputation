"""Resolve public Polymarket.com URLs for markets."""

POLYMARKET_BASE = "https://polymarket.com"


def get_polymarket_embed_slug(market):
    """Slug used by embed.polymarket.com — prefer Polymarket-native slug."""
    if market.polymarket_slug:
        return market.polymarket_slug
    raw_slug = (market.polymarket_raw or {}).get("slug")
    if raw_slug:
        return raw_slug
    return market.slug


def get_parent_event_slug(market):
    """Parent event slug from stored API payloads, if this market belongs to a group."""
    raw = market.polymarket_raw or {}
    event_raw = market.polymarket_event_raw or {}

    events = raw.get("events") or []
    if events and isinstance(events[0], dict):
        slug = events[0].get("slug")
        if slug:
            return slug

    return event_raw.get("slug") or ""


def resolve_polymarket_public_url(market):
    """
    Best URL for viewing this market on polymarket.com.

    Grouped sub-markets (e.g. 'NVIDIA' under 'Largest Company end of May')
    must link to the parent /event/ page — /event/{market-slug} 404s.
    Standalone binary markets use /event/{slug}.
    """
    market_slug = get_polymarket_embed_slug(market)
    if not market_slug:
        return ""

    parent_slug = get_parent_event_slug(market)

    if parent_slug and parent_slug != market_slug:
        return f"{POLYMARKET_BASE}/event/{parent_slug}"

    raw = market.polymarket_raw or {}
    if raw.get("groupItemTitle"):
        # Grouped sub-market — /event/{market-slug} 404s; /market/ works
        return f"{POLYMARKET_BASE}/market/{market_slug}"

    return f"{POLYMARKET_BASE}/event/{market_slug}"


def resolve_polymarket_market_url(market):
    """Direct link to a specific outcome market page (/market/{slug})."""
    market_slug = get_polymarket_embed_slug(market)
    if not market_slug:
        return ""
    return f"{POLYMARKET_BASE}/market/{market_slug}"
