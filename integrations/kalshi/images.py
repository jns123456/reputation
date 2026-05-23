"""Resolve Kalshi market/event images from metadata API payloads."""

GENERIC_ICON_HOST = "kalshi-fallback-images.s3.amazonaws.com"
GENERIC_ICON_PATH = "/structured_icons/"


def _is_generic_kalshi_fallback_icon(url):
    """True for Kalshi placeholder icons (hashtag, percentage, etc.)."""
    if not url or not isinstance(url, str):
        return False
    return GENERIC_ICON_HOST in url and GENERIC_ICON_PATH in url


def resolve_kalshi_market_image(market):
    """Return the best image URL for a Kalshi market card."""
    ticker = market.kalshi_ticker or market.external_id
    event_payload = market.kalshi_event_raw or {}
    metadata = event_payload.get("metadata") if isinstance(event_payload, dict) else {}

    if isinstance(metadata, dict):
        detail_image = ""
        for detail in metadata.get("market_details") or []:
            if not isinstance(detail, dict):
                continue
            if detail.get("market_ticker") == ticker and detail.get("image_url"):
                detail_image = detail["image_url"]
                break

        if detail_image and not _is_generic_kalshi_fallback_icon(detail_image):
            return detail_image

        for key in ("featured_image_url", "image_url"):
            candidate = metadata.get(key)
            if candidate and not _is_generic_kalshi_fallback_icon(candidate):
                return candidate

        if detail_image:
            return detail_image

        for key in ("featured_image_url", "image_url"):
            if metadata.get(key):
                return metadata[key]

    raw = market.kalshi_raw or {}
    for key in ("image", "icon", "image_url"):
        if raw.get(key):
            return raw[key]

    return ""
