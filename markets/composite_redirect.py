"""Redirect orphan Polymarket binary legs to their composite parent market."""

from __future__ import annotations

from integrations.polymarket.constants import (
    MULTI_OUTCOME_EVENT_KIND,
    POLYMARKET_EVENT_EXTERNAL_PREFIX,
)
from integrations.polymarket.client import is_multi_outcome_event_record
from integrations.polymarket.soccer_matches import (
    MONEYLINE_TYPE,
    WORLD_CUP_MATCH_EXTERNAL_PREFIX,
    is_soccer_match_event,
)
from markets.forecast_modes import ForecastMode, get_forecast_mode
from markets.models import Market


def _parent_event_slug(market) -> str:
    event_raw = market.polymarket_event_raw or {}
    slug = event_raw.get("slug")
    if slug:
        return str(slug).strip()

    raw = market.polymarket_raw or {}
    slug = raw.get("event_slug")
    if slug:
        return str(slug).strip()

    for embedded in raw.get("events") or []:
        if isinstance(embedded, dict) and embedded.get("slug"):
            return str(embedded["slug"]).strip()
    return ""


def composite_external_id_for_event(event: dict) -> str | None:
    slug = event.get("slug")
    if not slug:
        return None
    markets = event.get("markets")
    if markets is not None and not all(isinstance(item, dict) for item in markets):
        return None
    if is_soccer_match_event(event):
        return f"{WORLD_CUP_MATCH_EXTERNAL_PREFIX}{slug}"
    if is_multi_outcome_event_record(event, min_outcomes=2, require_open=False):
        return f"{POLYMARKET_EVENT_EXTERNAL_PREFIX}{slug}"
    return None


def _candidate_composite_external_ids(event_slug: str) -> tuple[str, ...]:
    return (
        f"{WORLD_CUP_MATCH_EXTERNAL_PREFIX}{event_slug}",
        f"{POLYMARKET_EVENT_EXTERNAL_PREFIX}{event_slug}",
    )


def is_orphan_polymarket_leg(market) -> bool:
    """True when this market looks like a child leg of a grouped Polymarket event."""
    if market.source != Market.Source.POLYMARKET:
        return False
    if get_forecast_mode(market) != ForecastMode.BINARY:
        return False

    external_id = market.external_id or ""
    if external_id.startswith(WORLD_CUP_MATCH_EXTERNAL_PREFIX) or external_id.startswith(
        POLYMARKET_EVENT_EXTERNAL_PREFIX
    ):
        return False

    raw = market.polymarket_raw or {}
    market_kind = raw.get("market_kind")
    if market_kind in {MULTI_OUTCOME_EVENT_KIND, "soccer_match_3way"}:
        return False

    if raw.get("groupItemTitle"):
        return True
    if raw.get("sportsMarketType") == MONEYLINE_TYPE:
        return True

    event = market.polymarket_event_raw or {}
    if event.get("markets") and composite_external_id_for_event({**event, "slug": _parent_event_slug(market) or event.get("slug")}):
        return True

    return False


def get_composite_redirect_market(market) -> Market | None:
    """Return the composite market that replaces this orphan leg, if any."""
    if not is_orphan_polymarket_leg(market):
        return None

    event_slug = _parent_event_slug(market)
    if not event_slug:
        return None

    event = dict(market.polymarket_event_raw or {})
    if not event.get("slug"):
        event["slug"] = event_slug

    composite_external_id = composite_external_id_for_event(event)
    if not composite_external_id:
        for candidate in _candidate_composite_external_ids(event_slug):
            if Market.objects.filter(external_id=candidate).exclude(pk=market.pk).exists():
                composite_external_id = candidate
                break

    if not composite_external_id:
        return None

    return (
        Market.objects.filter(external_id=composite_external_id)
        .exclude(pk=market.pk)
        .only("pk", "slug", "external_id")
        .first()
    )
