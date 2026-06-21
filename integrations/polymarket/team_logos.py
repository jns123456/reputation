"""Resolve Polymarket sports team logos (country flags for FIFA matches)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Polymarket event tag slugs → teams API ``league`` parameter.
EVENT_TAG_TO_TEAM_LEAGUE = {
    "fifa-world-cup": "fifwc",
    "2026-fifa-world-cup": "fifwc",
    "fifa-friendlies": "fif",
    "epl": "epl",
    "la-liga": "lal",
    "mls": "mls",
    "ucl": "ucl",
    "soccer": "soccer",
}

GENERIC_SOCCER_LOGO_MARKERS = ("soccer ball", "soccer+ball")


def is_usable_team_logo(url: str) -> bool:
    if not url:
        return False
    lowered = url.lower()
    return not any(marker in lowered for marker in GENERIC_SOCCER_LOGO_MARKERS)


def infer_team_league_from_event(event: dict) -> str | None:
    slug = (event.get("slug") or "").lower()
    if slug.startswith("fifwc-"):
        return "fifwc"

    tag_slugs = {
        tag.get("slug")
        for tag in (event.get("tags") or [])
        if isinstance(tag, dict) and tag.get("slug")
    }
    for tag_slug, league in EVENT_TAG_TO_TEAM_LEAGUE.items():
        if tag_slug in tag_slugs:
            return league
    return None


def _pick_best_team_logo(teams: list[dict], *, preferred_league: str | None) -> str:
    if not teams:
        return ""

    ordered = teams
    if preferred_league:
        preferred = [team for team in teams if team.get("league") == preferred_league]
        if preferred:
            ordered = preferred

    for team in ordered:
        logo = team.get("logo") or ""
        if is_usable_team_logo(logo):
            return logo
    return ""


class TeamLogoResolver:
    """In-memory cache for Polymarket ``/teams`` lookups during a sync batch."""

    def __init__(self, client):
        self.client = client
        self._cache: dict[tuple[str, str | None], str] = {}

    def resolve(self, team_name: str, *, league: str | None = None) -> str:
        name = (team_name or "").strip()
        if not name:
            return ""

        cache_key = (name.casefold(), league)
        if cache_key in self._cache:
            return self._cache[cache_key]

        logo = ""
        try:
            if league:
                teams = self.client.fetch_teams_by_name(name, league=league)
                logo = _pick_best_team_logo(teams, preferred_league=league)
            if not logo:
                teams = self.client.fetch_teams_by_name(name)
                logo = _pick_best_team_logo(teams, preferred_league=league)
        except Exception:
            logger.warning("Failed to resolve team logo for %s", name, exc_info=True)

        self._cache[cache_key] = logo
        return logo


def apply_team_logos_to_soccer_match(
    event: dict,
    normalized: dict,
    raw_market: dict,
    resolver: TeamLogoResolver,
) -> None:
    """Attach team flag URLs to import payloads (``outcomes`` + ``polymarket_raw``)."""
    team_a = raw_market.get("team_a") or ""
    team_b = raw_market.get("team_b") or ""
    league = infer_team_league_from_event(event)
    icon_a = resolver.resolve(team_a, league=league) if team_a else ""
    icon_b = resolver.resolve(team_b, league=league) if team_b else ""

    raw_market["team_a_icon"] = icon_a
    raw_market["team_b_icon"] = icon_b

    enriched_outcomes = []
    for item in normalized.get("outcomes") or []:
        label = item.get("label") if isinstance(item, dict) else str(item)
        entry = {"label": label}
        if label == team_a and icon_a:
            entry["icon"] = icon_a
        elif label == team_b and icon_b:
            entry["icon"] = icon_b
        enriched_outcomes.append(entry)
    normalized["outcomes"] = enriched_outcomes


def prepare_soccer_match_import(
    event: dict,
    *,
    default_category: str = "Sports",
    client=None,
    logo_resolver: TeamLogoResolver | None = None,
):
    """Normalize a soccer match event and enrich it with team flag URLs."""
    from integrations.polymarket.soccer_matches import (
        build_soccer_match_raw,
        normalize_soccer_match_event,
    )

    normalized = normalize_soccer_match_event(event, default_category=default_category)
    if not normalized:
        return None, None

    raw_market = build_soccer_match_raw(event, normalized=normalized)
    if client is not None or logo_resolver is not None:
        resolver = logo_resolver or TeamLogoResolver(client)
        apply_team_logos_to_soccer_match(event, normalized, raw_market, resolver)
    return normalized, raw_market
