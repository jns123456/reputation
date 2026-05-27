"""Build URLs for Polymarket's official embed widget (https://embed.polymarket.com/)."""

from urllib.parse import urlencode

from django.conf import settings

from integrations.polymarket.soccer_matches import is_world_cup_match_market
from integrations.polymarket.urls import (
    get_polymarket_embed_slug,
    resolve_polymarket_public_url,
)


def _encode_embed_url(base_url, params, *, overrides=None):
    params.update({k: v for k, v in (overrides or {}).items() if v is not None})
    params = {k: v for k, v in params.items() if v not in ("", None, False)}
    return f"{base_url.rstrip('/')}?{urlencode(params)}"


def build_polymarket_embed_url(market_slug, **overrides):
    """
    Build iframe src for a standard Polymarket binary market embed.

    See: https://embed.polymarket.com/ and Polymarket Help Center embed docs.
    """
    params = {
        "market": market_slug,
        "theme": settings.POLYMARKET_EMBED_THEME,
        "features": settings.POLYMARKET_EMBED_FEATURES,
        "layout": settings.POLYMARKET_EMBED_LAYOUT,
        "width": settings.POLYMARKET_EMBED_CONTENT_WIDTH,
    }
    if settings.POLYMARKET_EMBED_BORDER:
        params["border"] = "true"
    return _encode_embed_url(settings.POLYMARKET_EMBED_BASE_URL, params, overrides=overrides)


def build_polymarket_sports_embed_url(event_slug, **overrides):
    """
    Build iframe src for a Polymarket sports match event embed.

    FIFA World Cup and other 3-way moneyline events are event pages on
    polymarket.com — the /market embed returns "Market not found" for them.
    """
    params = {
        "market": event_slug,
        "theme": settings.POLYMARKET_EMBED_THEME,
        "width": settings.POLYMARKET_EMBED_CONTENT_WIDTH,
        "height": settings.POLYMARKET_EMBED_HEIGHT,
        "buttons": "false",
    }
    if settings.POLYMARKET_EMBED_BORDER:
        params["border"] = "true"
    return _encode_embed_url(settings.POLYMARKET_SPORTS_EMBED_BASE_URL, params, overrides=overrides)


def build_polymarket_embed_context(market):
    """Context dict for the embed partial template."""
    slug = get_polymarket_embed_slug(market)
    if not slug or market.source != market.Source.POLYMARKET:
        return None

    if is_world_cup_match_market(market):
        build_url = build_polymarket_sports_embed_url
    else:
        build_url = build_polymarket_embed_url

    embed_url_light = build_url(slug, theme="light")
    embed_url_dark = build_url(slug, theme="dark")

    return {
        "embed_url": embed_url_light,
        "embed_url_light": embed_url_light,
        "embed_url_dark": embed_url_dark,
        "embed_slug": slug,
        "embed_width": settings.POLYMARKET_EMBED_WIDTH,
        "embed_height": settings.POLYMARKET_EMBED_HEIGHT,
        "polymarket_url": resolve_polymarket_public_url(market),
        "embed_generator_url": "https://embed.polymarket.com/",
    }
