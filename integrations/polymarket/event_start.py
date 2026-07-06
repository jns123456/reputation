"""Resolve scheduled event start times for forecast kickoff gating."""

from __future__ import annotations

from datetime import datetime

from integrations.polymarket.client import (
    SPORTS_GAME_START_MAX_EARLY_DELTA,
    _coherent_game_start_time,
    _looks_like_sports_market,
    _parse_date,
)
from integrations.polymarket.f1_markets import (
    f1_race_start_from_market,
    f1_race_start_time,
    is_f1_race_event,
)

_LIVE_EVENT_TAG_SLUGS = frozenset(
    {
        "sports",
        "nba",
        "nfl",
        "mlb",
        "nhl",
        "ufc",
        "mma",
        "tennis",
        "soccer",
        "f1",
        "formula1",
        "grand-prix",
        "esports",
        "cricket",
        "games",
    }
)


def _collect_event_tag_slugs(event: dict) -> set[str]:
    slugs: set[str] = set()
    for tag in event.get("tags") or []:
        if isinstance(tag, dict):
            slug = tag.get("slug")
            if slug:
                slugs.add(str(slug).casefold())
        elif tag:
            slugs.add(str(tag).casefold())
    return slugs


def _grouped_event_has_live_cutoff(event: dict, grouped_markets: list[dict]) -> bool:
    if is_f1_race_event(event):
        return True
    if _looks_like_sports_market(event):
        return True
    if _collect_event_tag_slugs(event).intersection(_LIVE_EVENT_TAG_SLUGS):
        return True
    return any(raw_market.get("sportsMarketType") for raw_market in grouped_markets or [])


def grouped_event_start_time(
    event: dict,
    *,
    close_date: datetime | None,
    grouped_markets: list[dict],
) -> datetime | None:
    """Best scheduled start for a grouped Polymarket event."""
    start = _parse_date(event.get("gameStartTime"))
    if start:
        return start

    if is_f1_race_event(event):
        return f1_race_start_time(event, close_date=close_date)

    candidates: list[datetime] = []
    for raw_market in grouped_markets or []:
        coherent = _coherent_game_start_time(raw_market, close_date)
        if coherent:
            candidates.append(coherent)
    if candidates:
        return min(candidates)

    if _grouped_event_has_live_cutoff(event, grouped_markets):
        return close_date or _parse_date(event.get("endDate"))

    return None


def _infer_start_from_raw_payloads(market) -> datetime | None:
    event_raw = market.polymarket_event_raw or {}
    start = _parse_date(event_raw.get("gameStartTime"))
    if start:
        return start

    raw = market.polymarket_raw or {}
    kickoff = raw.get("kickoff_at")
    if kickoff:
        parsed = _parse_date(kickoff)
        if parsed:
            return parsed

    close_date = market.close_date
    coherent = _coherent_game_start_time(raw, close_date)
    if coherent:
        return coherent

    if is_f1_race_event(event_raw):
        return f1_race_start_from_market(market)

    f1_start = f1_race_start_from_market(market)
    if f1_start:
        return f1_start

    if event_raw and _grouped_event_has_live_cutoff(event_raw, event_raw.get("markets") or []):
        return close_date or _parse_date(event_raw.get("endDate"))

    if raw.get("sportsMarketType") or _looks_like_sports_market(raw):
        if close_date:
            return close_date
        game_start = _parse_date(raw.get("gameStartTime"))
        if game_start and close_date and game_start < close_date - SPORTS_GAME_START_MAX_EARLY_DELTA:
            return close_date
        return game_start

    return None


def resolve_market_event_start_time(market) -> datetime | None:
    """Scheduled start used to block new forecasts once an event is underway."""
    if market.game_start_time:
        return market.game_start_time

    if market._card_payloads_deferred():
        return market.close_date

    inferred = _infer_start_from_raw_payloads(market)
    if inferred:
        return inferred

    return market.close_date


def resolve_import_game_start_time(data: dict) -> datetime | None:
    """Persist the best-known event start on import/sync."""
    return data.get("game_start_time") or data.get("close_date")
