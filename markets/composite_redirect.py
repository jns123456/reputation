"""Redirect orphan Polymarket binary legs to their composite parent market."""

from __future__ import annotations

from django.db.models import Q

from integrations.polymarket.constants import (
    MULTI_OUTCOME_EVENT_KIND,
    POLYMARKET_EVENT_EXTERNAL_PREFIX,
)
from integrations.polymarket.client import is_multi_outcome_event_record
from integrations.polymarket.head_to_head_matches import (
    H2H_MATCH_EXTERNAL_PREFIX,
    is_h2h_match_event,
)
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
    if is_h2h_match_event(event):
        return f"{H2H_MATCH_EXTERNAL_PREFIX}{slug}"
    if is_multi_outcome_event_record(event, min_outcomes=2, require_open=False):
        return f"{POLYMARKET_EVENT_EXTERNAL_PREFIX}{slug}"
    return None


def _candidate_composite_external_ids(event_slug: str) -> tuple[str, ...]:
    return (
        f"{WORLD_CUP_MATCH_EXTERNAL_PREFIX}{event_slug}",
        f"{H2H_MATCH_EXTERNAL_PREFIX}{event_slug}",
        f"{POLYMARKET_EVENT_EXTERNAL_PREFIX}{event_slug}",
    )


def is_orphan_polymarket_leg(market) -> bool:
    """True when this market looks like a child leg of a grouped Polymarket event."""
    if market.source != Market.Source.POLYMARKET:
        return False
    if get_forecast_mode(market) != ForecastMode.BINARY:
        return False

    external_id = market.external_id or ""
    if (
        external_id.startswith(WORLD_CUP_MATCH_EXTERNAL_PREFIX)
        or external_id.startswith(H2H_MATCH_EXTERNAL_PREFIX)
        or external_id.startswith(POLYMARKET_EVENT_EXTERNAL_PREFIX)
    ):
        return False

    raw = market.polymarket_raw or {}
    market_kind = raw.get("market_kind")
    if market_kind in {MULTI_OUTCOME_EVENT_KIND, "soccer_match_3way", "h2h_match_2way"}:
        return False

    if raw.get("groupItemTitle"):
        return True
    if raw.get("sportsMarketType") == MONEYLINE_TYPE:
        return True

    event = market.polymarket_event_raw or {}
    if event.get("markets") and composite_external_id_for_event({**event, "slug": _parent_event_slug(market) or event.get("slug")}):
        return True

    return False


def orphan_polymarket_leg_q() -> Q:
    """ORM filter matching ``is_orphan_polymarket_leg`` for positive matches only.

    Prefer ``exclude_orphan_polymarket_legs`` for list querysets: ``exclude(Q)`` on
    JSON lookups is not NULL-safe on SQLite (drops standalone Polymarket rows).
    """
    composite_external = (
        Q(external_id__startswith=WORLD_CUP_MATCH_EXTERNAL_PREFIX)
        | Q(external_id__startswith=H2H_MATCH_EXTERNAL_PREFIX)
        | Q(external_id__startswith=POLYMARKET_EVENT_EXTERNAL_PREFIX)
    )

    grouped_leg = (
        Q(source=Market.Source.POLYMARKET)
        & Q(polymarket_raw__has_key="groupItemTitle")
        & ~Q(polymarket_raw__groupItemTitle="")
        & ~composite_external
    )
    moneyline_leg = (
        Q(source=Market.Source.POLYMARKET)
        & Q(polymarket_raw__sportsMarketType=MONEYLINE_TYPE)
        & ~composite_external
    )
    return grouped_leg | moneyline_leg


def _orphan_polymarket_leg_sql() -> str:
    """Vendor-specific SQL predicate for orphan legs (NULL-safe for ``exclude``)."""
    from django.db import connection

    composite_guard = (
        "external_id NOT LIKE 'wc-match:%%' AND external_id NOT LIKE 'h2h-match:%%' "
        "AND external_id NOT LIKE 'pm-event:%%'"
    )
    if connection.vendor == "postgresql":
        payload = """
            COALESCE(polymarket_raw->>'groupItemTitle', '') <> ''
            OR COALESCE(polymarket_raw->>'sportsMarketType', '') = %s
        """
    else:
        payload = """
            COALESCE(json_extract(polymarket_raw, '$.groupItemTitle'), '') <> ''
            OR COALESCE(json_extract(polymarket_raw, '$.sportsMarketType'), '') = %s
        """
    return f"""
        source = 'polymarket'
        AND {composite_guard}
        AND ({payload})
    """


def exclude_orphan_polymarket_legs(qs):
    """Drop Polymarket submarkets that belong to a composite parent event."""
    sql = _orphan_polymarket_leg_sql()
    return qs.extra(where=[f"NOT ({sql})"], params=[MONEYLINE_TYPE])


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
