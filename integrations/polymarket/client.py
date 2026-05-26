"""Polymarket API client — read-only market import."""

import json
import logging
from datetime import datetime

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)

ECONOMY_TAG_SLUG = "economy"
CRYPTO_TAG_SLUG = "crypto"


class PolymarketClient:
    def __init__(self, base_url=None):
        self.base_url = (base_url or settings.POLYMARKET_API_URL).rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def fetch_markets(self, limit=50, offset=0, active=True):
        params = {"limit": limit, "offset": offset}
        if active is not None:
            params["active"] = str(active).lower()
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

    def fetch_binary_markets_by_tag(
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
        binary_markets = []
        seen_ids = set()

        for event in events:
            for market in event.get("markets") or []:
                if not is_binary_market_record(market) or market.get("closed"):
                    continue
                market_id = market.get("id")
                if market_id in seen_ids:
                    continue
                enriched = dict(market)
                if default_category:
                    enriched.setdefault("category", default_category)
                enriched["volume24hr"] = market.get("volume24hr") or event.get("volume24hr")
                binary_markets.append(enriched)
                seen_ids.add(market_id)
                if len(binary_markets) >= limit:
                    return binary_markets[:limit]

        fallback_token = (fallback_tag_in_payload or tag_slug).lower()
        if len(binary_markets) < limit:
            standalone = self.fetch_markets(limit=limit * 3, active=True)
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
                    binary_markets.append(enriched)
                    seen_ids.add(market_id)
                    if len(binary_markets) >= limit:
                        break

        return binary_markets[:limit]

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

    def fetch_world_cup_match_events(self, *, limit=None, tag_slug=None):
        """Fetch FIFA World Cup group-stage match events with 3-way moneyline markets."""
        from integrations.polymarket.soccer_matches import (
            WORLD_CUP_MATCH_TAG_SLUG,
            is_world_cup_match_event,
        )

        tag_slug = tag_slug or WORLD_CUP_MATCH_TAG_SLUG
        matches = []
        seen_slugs = set()

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
            if not is_world_cup_match_event(event):
                continue
            matches.append(event)
            seen_slugs.add(slug)
            if limit is not None and len(matches) >= limit:
                break

        matches.sort(key=lambda event: event.get("startDate") or event.get("endDate") or "")
        return matches

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

    resolved_outcome = ""
    if resolved:
        resolved_outcome = raw.get("resolvedOutcome") or raw.get("winning_outcome") or ""
        if not resolved_outcome and tokens:
            for token in tokens:
                if isinstance(token, dict) and token.get("winner"):
                    resolved_outcome = token.get("outcome") or token.get("name", "")

    end_date = raw.get("endDate") or raw.get("end_date_iso") or raw.get("closeTime")
    close_date = _parse_date(end_date)

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
        "polymarket_slug": raw.get("slug", "")[:550],
    }


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
