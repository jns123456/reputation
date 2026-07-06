"""Polymarket Formula 1 race markets — forecast cutoff at scheduled race start."""

from __future__ import annotations

from datetime import datetime

from integrations.polymarket.client import _parse_date

F1_TAG_SLUGS = frozenset({"f1", "formula1"})
F1_RACE_TAG_SLUGS = frozenset({"grand-prix"})
F1_RACE_TITLE_MARKER = "grand prix"


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


def _collect_market_tag_slugs(market) -> set[str]:
    from markets.categories import _collect_tag_slugs

    return {slug.casefold() for slug in _collect_tag_slugs(market)}


def is_f1_event(event: dict) -> bool:
    """True when a Polymarket event is tagged as Formula 1."""
    return bool(_collect_event_tag_slugs(event).intersection(F1_TAG_SLUGS))


def is_f1_race_event(event: dict) -> bool:
    """True for single-race F1 events (Grand Prix props), not season-long futures."""
    if not is_f1_event(event):
        return False
    tags = _collect_event_tag_slugs(event)
    if tags.intersection(F1_RACE_TAG_SLUGS):
        return True
    title = (event.get("title") or "").casefold()
    return F1_RACE_TITLE_MARKER in title


def is_f1_market(market) -> bool:
    """True when a stored market belongs to Formula 1."""
    if "formula-1" in (getattr(market, "browse_area_slugs", None) or []):
        return True
    return bool(_collect_market_tag_slugs(market).intersection(F1_TAG_SLUGS))


def is_f1_race_market(market) -> bool:
    """True for stored single-race F1 markets (Grand Prix props)."""
    if not is_f1_market(market):
        return False
    tags = _collect_market_tag_slugs(market)
    if tags.intersection(F1_RACE_TAG_SLUGS):
        return True
    title = (getattr(market, "title", "") or "").casefold()
    return F1_RACE_TITLE_MARKER in title


def f1_race_start_time(event: dict, *, close_date: datetime | None = None) -> datetime | None:
    """Return the scheduled race start for an F1 Grand Prix event.

    Polymarket F1 payloads usually omit ``gameStartTime`` on the event. Sub-market
    ``gameStartTime`` values reflect when trading opened, not the race itself.
    The event/sub-market ``endDate`` (also our grouped ``close_date``) is the
    reliable race-start cutoff — same moment we use to stop new forecasts.
    """
    kickoff = _parse_date(event.get("gameStartTime"))
    if kickoff:
        return kickoff
    if close_date:
        return close_date
    return _parse_date(event.get("endDate"))


def f1_race_start_from_market(market):
    """Runtime backstop for stored F1 race rows missing ``game_start_time``."""
    if not is_f1_race_market(market):
        return None
    return market.close_date
