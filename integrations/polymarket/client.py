"""Polymarket API client — read-only market import."""

import json
import logging
import re
from datetime import datetime
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from integrations.polymarket.constants import (
    MULTI_OUTCOME_CHART_OUTCOMES,
    MULTI_OUTCOME_EVENT_KIND,
    POLYMARKET_EVENT_EXTERNAL_PREFIX,
)

logger = logging.getLogger(__name__)

ECONOMY_TAG_SLUG = "economy"
CRYPTO_TAG_SLUG = "crypto"
SPORTS_GAME_START_MAX_EARLY_DELTA = timedelta(hours=12)
DATE_IN_TEXT_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")


def is_multi_outcome_event_market(market) -> bool:
    """True for composite Polymarket grouped events stored as one internal market."""
    return (market.polymarket_raw or {}).get("market_kind") == MULTI_OUTCOME_EVENT_KIND


class PolymarketClient:
    def __init__(self, base_url=None):
        self.base_url = (base_url or settings.POLYMARKET_API_URL).rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def fetch_markets(
        self,
        limit=50,
        offset=0,
        active=True,
        closed=None,
        order=None,
    ):
        params = {"limit": limit, "offset": offset}
        if active is not None:
            params["active"] = str(active).lower()
        if closed is not None:
            params["closed"] = str(closed).lower()
        if order:
            params["order"] = order
            params["ascending"] = "false"
        url = f"{self.base_url}/markets"
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list):
            return data
        return data.get("data", data.get("markets", []))

    def fetch_events(self, *, tag_slug=None, limit=50, offset=0, active=True, closed=False, order=None):
        params = {"limit": limit, "offset": offset}
        if active is not None:
            params["active"] = str(active).lower()
        if closed is not None:
            params["closed"] = str(closed).lower()
        if tag_slug:
            params["tag_slug"] = tag_slug
        if order:
            params["order"] = order
            params["ascending"] = "false"
        url = f"{self.base_url}/events"
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list):
            return data
        return data.get("data", data.get("events", []))

    def fetch_events_paginated(
        self,
        *,
        tag_slug=None,
        page_size=100,
        max_pages=50,
        active=True,
        closed=False,
        order=None,
    ):
        """Fetch all events for a tag, following Polymarket offset pagination."""
        all_events = []
        offset = 0

        for _ in range(max_pages):
            events = self.fetch_events(
                tag_slug=tag_slug,
                limit=page_size,
                offset=offset,
                active=active,
                closed=closed,
                order=order,
            )
            if not events:
                break
            all_events.extend(events)
            if len(events) < page_size:
                break
            offset += page_size

        return all_events

    def fetch_binary_market_pairs_by_tag(
        self,
        tag_slug,
        *,
        limit=20,
        default_category="",
        fallback_tag_in_payload=None,
    ):
        """Fetch active binary Yes/No markets for a Polymarket tag slug."""
        events = self.fetch_events(
            tag_slug=tag_slug,
            limit=max(limit * 2, 30),
            active=True,
            closed=False,
            order="volume24hr",
        )
        seen_ids = set()
        pairs = collect_binary_market_pairs_from_events(
            events,
            seen_ids=seen_ids,
            limit=limit,
            default_category=default_category,
        )

        fallback_token = (fallback_tag_in_payload or tag_slug).lower()
        if len(pairs) < limit:
            standalone = self.fetch_markets(
                limit=limit * 3,
                active=True,
                closed=False,
                order="volumeNum",
            )
            for market in standalone:
                if not is_binary_market_record(market) or market.get("closed"):
                    continue
                market_id = market.get("id")
                if market_id in seen_ids:
                    continue
                category = str(market.get("category") or "").lower()
                tags = json.dumps(market.get("tags") or []).lower()
                if category == fallback_token or fallback_token in tags:
                    enriched = dict(market)
                    if default_category:
                        enriched.setdefault("category", default_category)
                    raw_event = _embedded_event_for_market(enriched)
                    pairs.append((enriched, raw_event))
                    seen_ids.add(market_id)
                    if len(pairs) >= limit:
                        break

        return pairs[:limit]

    def fetch_market_pairs_by_tag(
        self,
        tag_slug,
        *,
        limit=20,
        default_category="",
        max_event_pages=10,
    ):
        """Fetch importable markets for a tag, prioritizing total volume then 24h volume."""
        pairs = []
        seen_ids = set()

        for order in ("volume", "volume24hr"):
            events = self.fetch_events_paginated(
                tag_slug=tag_slug,
                page_size=100,
                max_pages=max_event_pages,
                active=True,
                closed=False,
                order=order,
            )
            batch = collect_importable_market_pairs_from_events(
                events,
                seen_ids=seen_ids,
                limit=limit - len(pairs),
                default_category=default_category,
            )
            pairs.extend(batch)
            if len(pairs) >= limit:
                break

        return pairs[:limit]

    def fetch_binary_markets_by_tag(
        self,
        tag_slug,
        *,
        limit=20,
        default_category="",
        fallback_tag_in_payload=None,
    ):
        """Fetch active binary Yes/No markets for a Polymarket tag slug."""
        pairs = self.fetch_binary_market_pairs_by_tag(
            tag_slug,
            limit=limit,
            default_category=default_category,
            fallback_tag_in_payload=fallback_tag_in_payload,
        )
        return [market for market, _event in pairs]

    def fetch_top_volume_market_pairs(
        self,
        *,
        min_volume_share=0.5,
        max_markets=500,
        max_event_pages=15,
        page_size=100,
    ):
        """
        Return (market, event) pairs from the highest-volume Polymarket events.

        Keeps importing events until their combined volume reaches ``min_volume_share``
        of the scanned catalog, then adds 24h-volume leaders not already included.
        """
        pairs = []
        seen_ids = set()

        standalone_cap = min(100, max(20, max_markets // 5))
        standalone_markets = self.fetch_markets(
            limit=standalone_cap,
            active=True,
            closed=False,
            order="volumeNum",
        )
        for market in standalone_markets:
            if not is_binary_market_record(market) or market.get("closed"):
                continue
            market_id = market.get("id")
            if not market_id or market_id in seen_ids:
                continue
            pairs.append((market, _embedded_event_for_market(market)))
            seen_ids.add(market_id)

        volume_events = self.fetch_events_paginated(
            page_size=page_size,
            max_pages=max_event_pages,
            active=True,
            closed=False,
            order="volume",
        )
        total_volume = sum(float(event.get("volume") or 0) for event in volume_events)
        target_volume = total_volume * min_volume_share if total_volume else 0
        cumulative_volume = 0.0

        for event in volume_events:
            batch = collect_importable_market_pairs_from_events(
                [event],
                seen_ids=seen_ids,
                default_category="",
            )
            pairs.extend(batch)
            cumulative_volume += float(event.get("volume") or 0)
            if len(pairs) >= max_markets:
                return pairs[:max_markets]
            if target_volume and cumulative_volume >= target_volume:
                break

        volume24_events = self.fetch_events_paginated(
            page_size=page_size,
            max_pages=max(5, max_event_pages // 3),
            active=True,
            closed=False,
            order="volume24hr",
        )
        for event in volume24_events:
            batch = collect_importable_market_pairs_from_events(
                [event],
                seen_ids=seen_ids,
                default_category="",
            )
            pairs.extend(batch)
            if len(pairs) >= max_markets:
                return pairs[:max_markets]

        return pairs[:max_markets]

    def fetch_economy_binary_markets(self, limit=20):
        """Fetch active binary Yes/No markets from Polymarket Economy category."""
        return self.fetch_binary_markets_by_tag(
            ECONOMY_TAG_SLUG,
            limit=limit,
            default_category="Economy",
            fallback_tag_in_payload="economy",
        )

    def fetch_crypto_binary_markets(self, limit=20):
        """Fetch active binary Yes/No markets from Polymarket Crypto category."""
        return self.fetch_binary_markets_by_tag(
            CRYPTO_TAG_SLUG,
            limit=limit,
            default_category="Crypto",
            fallback_tag_in_payload="crypto",
        )

    def fetch_soccer_match_events(self, *, limit=None, tag_slugs=None):
        """Fetch Polymarket soccer events with 3-way moneyline markets."""
        from integrations.polymarket.soccer_matches import (
            SOCCER_MATCH_TAG_SLUGS,
            is_soccer_match_event,
        )

        tag_slugs = tag_slugs or SOCCER_MATCH_TAG_SLUGS
        matches = []
        seen_slugs = set()

        for tag_slug in tag_slugs:
            events = self.fetch_events_paginated(
                tag_slug=tag_slug,
                page_size=100,
                max_pages=50,
                active=True,
                closed=False,
            )
            for event in events:
                slug = event.get("slug")
                if not slug or slug in seen_slugs:
                    continue
                if not is_soccer_match_event(event):
                    continue
                matches.append(event)
                seen_slugs.add(slug)
                if limit is not None and len(matches) >= limit:
                    break
            if limit is not None and len(matches) >= limit:
                break

        matches.sort(key=lambda event: event.get("startDate") or event.get("endDate") or "")
        return matches

    def fetch_h2h_match_events(self, *, limit=None, tag_slugs=None):
        """Fetch Polymarket events with a single 2-player moneyline (tennis, NBA, etc.)."""
        from integrations.polymarket.head_to_head_matches import (
            H2H_MATCH_TAG_SLUGS,
            is_h2h_match_event,
        )

        tag_slugs = tag_slugs or H2H_MATCH_TAG_SLUGS
        matches = []
        seen_slugs = set()

        for tag_slug in tag_slugs:
            events = self.fetch_events_paginated(
                tag_slug=tag_slug,
                page_size=100,
                max_pages=50,
                active=True,
                closed=False,
            )
            for event in events:
                slug = event.get("slug")
                if not slug or slug in seen_slugs:
                    continue
                if not is_h2h_match_event(event):
                    continue
                matches.append(event)
                seen_slugs.add(slug)
                if limit is not None and len(matches) >= limit:
                    break
            if limit is not None and len(matches) >= limit:
                break

        matches.sort(key=lambda event: event.get("startDate") or event.get("endDate") or "")
        return matches

    def fetch_world_cup_match_events(self, *, limit=None, tag_slug=None):
        """Fetch FIFA World Cup group-stage match events with 3-way moneyline markets."""
        from integrations.polymarket.soccer_matches import WORLD_CUP_MATCH_TAG_SLUG

        if tag_slug and tag_slug != WORLD_CUP_MATCH_TAG_SLUG:
            return self.fetch_soccer_match_events(limit=limit, tag_slugs=(tag_slug,))

        from integrations.polymarket.soccer_matches import WORLD_CUP_TAG_SLUGS

        return self.fetch_soccer_match_events(limit=limit, tag_slugs=WORLD_CUP_TAG_SLUGS)

    def fetch_market_by_id(self, external_id):
        url = f"{self.base_url}/markets/{external_id}"
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        raw = response.json()
        return self._enrich_market_with_events(raw)

    def fetch_market_by_slug(self, slug):
        url = f"{self.base_url}/markets"
        response = self.session.get(url, params={"slug": slug}, timeout=30)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and data:
            return data[0]
        return None

    def _enrich_market_with_events(self, raw):
        """Slug query includes parent events; single-market fetch often does not."""
        if raw.get("events"):
            return raw
        slug = raw.get("slug")
        if not slug:
            return raw
        try:
            enriched = self.fetch_market_by_slug(slug)
            if enriched and enriched.get("events"):
                raw = {**raw, "events": enriched["events"]}
        except Exception:
            logger.exception("Failed to enrich market with events for slug %s", slug)
        return raw

    def fetch_event_by_slug(self, slug):
        url = f"{self.base_url}/events/slug/{slug}"
        response = self.session.get(url, timeout=30)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()


def _embedded_event_for_market(raw_market):
    events = raw_market.get("events") or []
    if events and isinstance(events[0], dict):
        return events[0]
    return {}


def is_grouped_composite_event(event: dict) -> bool:
    """True when an event should be one internal market, not separate binary legs."""
    from integrations.polymarket.head_to_head_matches import is_h2h_match_event
    from integrations.polymarket.soccer_matches import is_soccer_match_event

    return (
        is_soccer_match_event(event)
        or is_h2h_match_event(event)
        or is_multi_outcome_event_record(
            event,
            min_outcomes=2,
            require_open=False,
        )
    )


def collect_binary_market_pairs_from_events(
    events,
    *,
    seen_ids=None,
    limit=None,
    default_category="",
):
    """Extract active binary markets from Polymarket events with parent event attached."""
    from integrations.polymarket.head_to_head_matches import (
        is_h2h_match_event,
        is_h2h_moneyline_submarket,
    )
    from integrations.polymarket.soccer_matches import (
        is_soccer_match_event,
        is_soccer_moneyline_submarket,
    )

    if seen_ids is None:
        seen_ids = set()

    pairs = []
    for event in events:
        if is_soccer_match_event(event) or is_h2h_match_event(event):
            continue
        composite_event = is_grouped_composite_event(event)
        skip_moneyline_legs = is_soccer_match_event(event)
        for market in event.get("markets") or []:
            if skip_moneyline_legs and is_soccer_moneyline_submarket(market, event):
                continue
            if is_h2h_moneyline_submarket(market, event):
                continue
            if composite_event and market.get("groupItemTitle"):
                continue
            if not is_binary_market_record(market) or market.get("closed"):
                continue
            market_id = market.get("id")
            if not market_id or market_id in seen_ids:
                continue
            enriched = dict(market)
            if default_category:
                enriched.setdefault("category", default_category)
            enriched["volume24hr"] = market.get("volume24hr") or event.get("volume24hr")
            pairs.append((enriched, event))
            seen_ids.add(market_id)
            if limit is not None and len(pairs) >= limit:
                return pairs
    return pairs


def collect_importable_market_pairs_from_events(
    events,
    *,
    seen_ids=None,
    limit=None,
    default_category="",
):
    """Extract composite multi-outcome events or individual binary markets."""
    from integrations.polymarket.head_to_head_matches import (
        build_h2h_match_raw,
        normalize_h2h_match_event,
    )
    from integrations.polymarket.soccer_matches import (
        build_soccer_match_raw,
        normalize_soccer_match_event,
    )

    if seen_ids is None:
        seen_ids = set()

    pairs = []
    for event in events:
        h2h = normalize_h2h_match_event(event, default_category=default_category)
        if h2h:
            external_id = h2h["external_id"]
            if external_id not in seen_ids:
                pairs.append((build_h2h_match_raw(event, normalized=h2h), event))
                seen_ids.add(external_id)
                if limit is not None and len(pairs) >= limit:
                    return pairs
            continue

        composite = normalize_polymarket_event_record(
            event,
            default_category=default_category,
            require_open=False,
        )
        if composite:
            external_id = composite["external_id"]
            if external_id not in seen_ids:
                pairs.append((build_polymarket_event_raw(event, normalized=composite), event))
                seen_ids.add(external_id)
                if limit is not None and len(pairs) >= limit:
                    return pairs
            continue

        soccer = normalize_soccer_match_event(event, default_category=default_category)
        if soccer:
            external_id = soccer["external_id"]
            if external_id not in seen_ids:
                pairs.append((build_soccer_match_raw(event, normalized=soccer), event))
                seen_ids.add(external_id)
                if limit is not None and len(pairs) >= limit:
                    return pairs
            continue

        batch = collect_binary_market_pairs_from_events(
            [event],
            seen_ids=seen_ids,
            limit=None if limit is None else limit - len(pairs),
            default_category=default_category,
        )
        pairs.extend(batch)
        if limit is not None and len(pairs) >= limit:
            return pairs

    return pairs


def _parse_json_field(value):
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return None


def is_binary_market_record(raw):
    """True when market has exactly Yes/No outcomes."""
    labels = _extract_outcome_labels(raw)
    if len(labels) != 2:
        return False
    normalized = {label.strip().lower() for label in labels}
    return normalized == {"yes", "no"}


def _extract_outcome_labels(raw):
    tokens = raw.get("tokens") or []
    if tokens:
        labels = []
        for token in tokens:
            if isinstance(token, dict):
                label = token.get("outcome") or token.get("name") or token.get("label", "")
                if label:
                    labels.append(str(label))
            elif isinstance(token, str):
                labels.append(token)
        if labels:
            return labels

    outcomes = _parse_json_field(raw.get("outcomes"))
    if isinstance(outcomes, list):
        labels = []
        for item in outcomes:
            if isinstance(item, dict):
                label = item.get("label") or item.get("outcome") or item.get("name", "")
            else:
                label = str(item)
            if label:
                labels.append(label)
        return labels

    return []


def _yes_token_id(raw_market: dict) -> str:
    ids = _parse_json_field(raw_market.get("clobTokenIds"))
    if isinstance(ids, list) and ids:
        return str(ids[0])
    for token in raw_market.get("tokens") or []:
        if not isinstance(token, dict):
            continue
        label = str(token.get("outcome") or token.get("name") or "").strip().lower()
        if label == "yes":
            token_id = token.get("token_id") or token.get("tokenId")
            if token_id:
                return str(token_id)
    return ""


def _outcome_market_meta(raw_market: dict) -> dict:
    return {
        "id": raw_market.get("id"),
        "conditionId": raw_market.get("conditionId"),
        "slug": raw_market.get("slug"),
        "yes_token_id": _yes_token_id(raw_market),
    }


def select_top_chart_outcomes(
    market,
    *,
    limit=MULTI_OUTCOME_CHART_OUTCOMES,
) -> list[dict]:
    """Top-N outcome markets by Yes probability for multi-outcome charts."""
    raw = market.polymarket_raw or {}
    stored = raw.get("chart_outcomes") or []
    if stored:
        return stored[:limit]

    probs = market.current_probability or {}
    outcome_markets = raw.get("outcome_markets") or {}
    items = []
    for label, probability in probs.items():
        meta = outcome_markets.get(label) or {}
        yes_token_id = meta.get("yes_token_id") or ""
        if not yes_token_id:
            continue
        try:
            prob = float(probability)
        except (TypeError, ValueError):
            continue
        items.append(
            {
                "label": label,
                "probability": prob,
                "slug": meta.get("slug") or "",
                "yes_token_id": yes_token_id,
            }
        )
    items.sort(key=lambda item: item["probability"], reverse=True)
    return items[:limit]


def _yes_price(raw_market: dict) -> float | None:
    labels = _extract_outcome_labels(raw_market)
    prices = _parse_json_field(raw_market.get("outcomePrices"))
    if not isinstance(prices, list) or not labels:
        return None
    for label, price in zip(labels, prices):
        if str(label).strip().lower() != "yes":
            continue
        try:
            return float(price)
        except (TypeError, ValueError):
            return None
    return None


_RESOLVED_YES_PRICE_THRESHOLD = 0.99


def _market_is_resolved(raw_market: dict) -> bool:
    """True when Polymarket has finished resolving a binary sub-market."""
    if raw_market.get("resolved") or raw_market.get("automaticallyResolved"):
        return True
    return str(raw_market.get("umaResolutionStatus") or "").lower() == "resolved"


def infer_binary_resolved_outcome(raw, labels=None):
    """Best-effort winning outcome for a resolved Polymarket binary market.

    Polymarket often omits ``resolvedOutcome`` on auto-resolved buckets and only
    sets ``outcomePrices`` to ``["1", "0"]`` — without this, forecasts stay pending
    while the market card already reads as resolved.
    """
    winning = str(raw.get("resolvedOutcome") or raw.get("winning_outcome") or "").strip()
    if winning:
        return winning[:255]

    for token in raw.get("tokens") or []:
        if isinstance(token, dict) and token.get("winner"):
            label = str(token.get("outcome") or token.get("name") or "").strip()
            if label:
                return label[:255]

    if not _market_is_resolved(raw):
        return ""

    labels = labels or _extract_outcome_labels(raw)
    yes_price = _yes_price(raw)
    if yes_price is None:
        return ""

    if yes_price >= _RESOLVED_YES_PRICE_THRESHOLD:
        for label in labels:
            if str(label).strip().lower() == "yes":
                return str(label)[:255]
        return "Yes"
    if yes_price <= (1 - _RESOLVED_YES_PRICE_THRESHOLD):
        for label in labels:
            if str(label).strip().lower() == "no":
                return str(label)[:255]
        return "No"
    return ""


def _market_is_resolved_yes(raw_market: dict) -> bool:
    """True when a grouped/binary sub-market resolved to Yes."""
    if not _market_is_resolved(raw_market):
        return False
    winning = str(raw_market.get("resolvedOutcome") or raw_market.get("winning_outcome") or "").lower()
    if winning == "yes":
        return True
    for token in raw_market.get("tokens") or []:
        if isinstance(token, dict) and token.get("winner"):
            label = str(token.get("outcome") or token.get("name") or "").lower()
            if label == "yes":
                return True
    yes_price = _yes_price(raw_market)
    return yes_price is not None and yes_price >= _RESOLVED_YES_PRICE_THRESHOLD


def _grouped_outcome_markets(event: dict, *, open_only: bool) -> list[dict]:
    markets = []
    seen_labels = set()
    for raw_market in event.get("markets") or []:
        if open_only and raw_market.get("closed"):
            continue
        label = str(raw_market.get("groupItemTitle") or "").strip()
        if not label or label in seen_labels:
            continue
        if raw_market.get("sportsMarketType"):
            continue
        if not is_binary_market_record(raw_market):
            continue
        markets.append(raw_market)
        seen_labels.add(label)
    return markets


def is_multi_outcome_event_record(
    event: dict,
    *,
    min_outcomes: int = 2,
    require_open: bool = False,
) -> bool:
    """True for Polymarket grouped events that can be represented as one forecast."""
    slug = event.get("slug") or event.get("id")
    if not slug:
        return False
    return len(_grouped_outcome_markets(event, open_only=require_open)) >= min_outcomes


def _latest_submarket_end_date(raw_markets: list[dict]):
    """Return the latest ``endDate`` found on grouped sub-markets."""
    dates = []
    for raw_market in raw_markets:
        parsed = _parse_date(raw_market.get("endDate"))
        if parsed:
            dates.append(parsed)
    return max(dates) if dates else None


def _grouped_event_close_date(
    event: dict,
    *,
    open_markets: list[dict],
    all_grouped_markets: list[dict],
):
    """Effective forecast cutoff for grouped multi-outcome events.

    Polymarket's event-level ``endDate`` can lag behind individual outcome
    buckets (e.g. Claude 5 keeps trading through September while the event
    payload still shows April). Prefer the latest open sub-market end date.
    """
    return (
        _latest_submarket_end_date(open_markets)
        or _latest_submarket_end_date(all_grouped_markets)
        or _parse_date(event.get("endDate") or event.get("closedTime") or event.get("startDate"))
    )


def normalize_polymarket_event_record(
    event: dict,
    *,
    default_category: str = "",
    require_open: bool = False,
) -> dict | None:
    """Convert a grouped Polymarket event into one internal multi-outcome market."""
    if not is_multi_outcome_event_record(event, require_open=require_open):
        return None

    slug = str(event.get("slug") or event.get("id"))
    title = event.get("title") or event.get("ticker") or "Untitled Event"
    description = event.get("description") or ""
    open_markets = _grouped_outcome_markets(event, open_only=True)
    all_grouped_markets = _grouped_outcome_markets(event, open_only=False)

    def sort_key(raw_market):
        threshold = raw_market.get("groupItemThreshold")
        try:
            return (0, int(threshold))
        except (TypeError, ValueError):
            return (1, str(raw_market.get("groupItemTitle") or ""))

    open_markets.sort(key=sort_key)
    all_grouped_markets.sort(key=sort_key)

    probabilities = {}
    outcome_markets = {}
    resolved_outcome = ""
    for raw_market in all_grouped_markets:
        label = str(raw_market.get("groupItemTitle") or "").strip()
        if not label:
            continue
        yes_price = _yes_price(raw_market)
        if yes_price is not None and not raw_market.get("closed"):
            probabilities[label] = yes_price
        outcome_markets[label] = _outcome_market_meta(raw_market)
        if _market_is_resolved_yes(raw_market):
            resolved_outcome = label

    if resolved_outcome:
        status = "resolved"
    elif not open_markets:
        status = "closed"
    else:
        status = "open"

    close_date = _grouped_event_close_date(
        event,
        open_markets=open_markets,
        all_grouped_markets=all_grouped_markets,
    )
    category = event.get("category") or default_category
    if isinstance(category, list):
        category = category[0] if category else default_category

    label_markets = open_markets if open_markets else all_grouped_markets
    outcome_labels = [str(raw_market.get("groupItemTitle")).strip() for raw_market in label_markets]
    return {
        "external_id": f"{POLYMARKET_EVENT_EXTERNAL_PREFIX}{slug}",
        "title": str(title)[:500],
        "description": description,
        "category": str(category or "")[:100],
        "source": "polymarket",
        "status": status,
        "outcomes": [{"label": label} for label in outcome_labels],
        "current_probability": probabilities,
        "close_date": close_date,
        "resolution_date": close_date if status == "resolved" else None,
        "resolved_outcome": resolved_outcome,
        "accepting_orders": _any_accepts_orders(open_markets),
        "game_start_time": _parse_date(event.get("gameStartTime")),
        "polymarket_slug": slug[:550],
    }


def build_polymarket_event_raw(event: dict, *, normalized: dict) -> dict:
    """Composite payload stored for grouped Polymarket multi-outcome events."""
    outcome_markets = {}
    chart_candidates = []
    for raw_market in _grouped_outcome_markets(event, open_only=False):
        label = str(raw_market.get("groupItemTitle") or "").strip()
        if not label:
            continue
        meta = _outcome_market_meta(raw_market)
        outcome_markets[label] = meta
        yes_price = _yes_price(raw_market)
        if yes_price is not None and not raw_market.get("closed") and meta.get("yes_token_id"):
            chart_candidates.append(
                {
                    "label": label,
                    "probability": yes_price,
                    "slug": meta.get("slug") or "",
                    "yes_token_id": meta["yes_token_id"],
                }
            )

    chart_candidates.sort(key=lambda item: item["probability"], reverse=True)
    chart_outcomes = chart_candidates[:MULTI_OUTCOME_CHART_OUTCOMES]

    return {
        "id": normalized["external_id"],
        "market_kind": MULTI_OUTCOME_EVENT_KIND,
        "event_id": event.get("id"),
        "event_slug": event.get("slug"),
        "slug": event.get("slug"),
        "question": normalized["title"],
        "title": normalized["title"],
        "description": normalized.get("description", ""),
        "category": normalized.get("category", ""),
        "volume": event.get("volume"),
        "volumeNum": event.get("volume"),
        "volume24hr": event.get("volume24hr"),
        "liquidity": event.get("liquidity"),
        "image": event.get("image") or event.get("icon"),
        "icon": event.get("icon") or event.get("image"),
        "outcome_markets": outcome_markets,
        "chart_outcomes": chart_outcomes,
    }


def normalize_polymarket_record(raw, *, default_category=""):
    """Convert a Polymarket API record into internal market dict."""
    external_id = str(raw.get("id") or raw.get("conditionId") or raw.get("slug", ""))
    if not external_id:
        raise ValueError("Polymarket record missing id")

    title = raw.get("question") or raw.get("title") or "Untitled Market"
    description = raw.get("description") or ""

    labels = _extract_outcome_labels(raw)
    outcomes = [{"label": label} for label in labels]
    probabilities = {}

    prices = _parse_json_field(raw.get("outcomePrices"))
    if isinstance(prices, list) and labels:
        for label, price in zip(labels, prices):
            try:
                probabilities[label] = float(price)
            except (TypeError, ValueError):
                continue

    tokens = raw.get("tokens") or []
    if not probabilities and tokens:
        for token in tokens:
            if isinstance(token, dict):
                label = token.get("outcome") or token.get("name") or token.get("label", "")
                price = token.get("price") or token.get("probability")
                if label and price is not None:
                    probabilities[label] = float(price)

    closed = raw.get("closed", False)
    resolved = raw.get("resolved", False) or raw.get("automaticallyResolved", False)

    if resolved:
        status = "resolved"
    elif closed:
        status = "closed"
    else:
        status = "open"

    resolved_outcome = infer_binary_resolved_outcome(raw, labels=labels) if resolved else ""

    end_date = raw.get("endDate") or raw.get("end_date_iso") or raw.get("closeTime")
    close_date = _parse_date(end_date)
    game_start_time = _coherent_game_start_time(raw, close_date)

    category = raw.get("category") or raw.get("groupItemTitle") or default_category
    if isinstance(category, list):
        category = category[0] if category else default_category

    return {
        "external_id": external_id,
        "title": title[:500],
        "description": description,
        "category": str(category)[:100],
        "source": "polymarket",
        "status": status,
        "outcomes": outcomes,
        "current_probability": probabilities,
        "close_date": close_date,
        "resolution_date": close_date if resolved else None,
        "resolved_outcome": str(resolved_outcome)[:255],
        "accepting_orders": _accepts_orders(raw),
        "game_start_time": game_start_time,
        "polymarket_slug": raw.get("slug", "")[:550],
    }


def _accepts_orders(raw):
    """Whether a single source market is still accepting orders.

    Polymarket flips ``acceptingOrders`` to false when a market stops trading
    (event started, suspended, or resolving) — typically before ``closed`` or
    ``resolved`` are set. A missing flag defaults to True so markets that do not
    carry it are not over-blocked.
    """
    value = raw.get("acceptingOrders")
    if value is None:
        return True
    return bool(value)


def _any_accepts_orders(raw_markets):
    """True if any sub-market of a grouped event still accepts orders."""
    if not raw_markets:
        return False
    return any(_accepts_orders(market) for market in raw_markets)


def _date_from_text(*values):
    for value in values:
        if not value:
            continue
        match = DATE_IN_TEXT_RE.search(str(value))
        if match:
            try:
                return datetime.fromisoformat(match.group(1)).date()
            except ValueError:
                continue
    return None


def _looks_like_sports_market(raw):
    if raw.get("sportsMarketType"):
        return True
    tags = json.dumps(raw.get("tags") or []).lower()
    category = str(raw.get("category") or "").lower()
    return "sport" in category or "sports" in tags


def _coherent_game_start_time(raw, close_date):
    """Return a kickoff timestamp only when it is consistent with market close.

    Some Polymarket sports records carry a stale ``gameStartTime`` that predates
    the actual event while ``closed=False`` and ``acceptingOrders=True``. In that
    case the market close/end date is the safer forecast cutoff.
    """
    game_start_time = _parse_date(raw.get("gameStartTime"))
    if not game_start_time or not close_date:
        return game_start_time

    market_date = _date_from_text(
        raw.get("question"),
        raw.get("title"),
        raw.get("slug"),
    )
    if market_date and game_start_time.date() < market_date <= close_date.date():
        return close_date

    if _looks_like_sports_market(raw) and game_start_time < close_date - SPORTS_GAME_START_MAX_EARLY_DELTA:
        return close_date

    return game_start_time


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        dt = parse_datetime(str(value))
        if dt is None:
            try:
                dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.utc)
    return dt
