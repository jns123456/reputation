"""Polymarket head-to-head sports matches (tennis, NBA, etc.) — single 2-outcome moneyline."""

import logging

from integrations.polymarket.client import (
    _any_accepts_orders,
    _extract_outcome_labels,
    _market_is_resolved_yes,
    _parse_date,
    _parse_json_field,
    _yes_token_id,
)
from integrations.polymarket.soccer_matches import MONEYLINE_TYPE, parse_match_teams

logger = logging.getLogger(__name__)

H2H_MATCH_EXTERNAL_PREFIX = "h2h-match:"
H2H_MATCH_KIND = "h2h_match_2way"
# Tags that carry live H2H match events on Polymarket (paginated like soccer matches).
# ``basketball`` is intentionally omitted: it mixes NBA with Euroleague/NCAA (~40+ events).
# NBA playoff games are tagged ``nba`` (typically only a few live at once).
# UFC fight nights use tag ``ufc`` (2-fighter moneyline, same shape as tennis/NBA).
# NFL/MLB/NHL use the same single moneyline (two team/player names) as NBA tennis.
H2H_MATCH_TAG_SLUGS = (
    "tennis",
    "nba",
    "ufc",
    "nfl",
    "mlb",
    "nhl",
)
# Team-vs-team esports moneylines on Polymarket share the same event shape as sports H2H.
ESPORTS_H2H_MATCH_TAG_SLUGS = ("esports",)

_RESOLVED_PRICE_THRESHOLD = 0.99


def is_h2h_match_market(market) -> bool:
    external_id = getattr(market, "external_id", "") or ""
    if external_id.startswith(H2H_MATCH_EXTERNAL_PREFIX):
        return True
    raw = getattr(market, "polymarket_raw", None) or {}
    return raw.get("market_kind") == H2H_MATCH_KIND


def _moneyline_markets(event: dict, *, open_only: bool) -> list[dict]:
    markets = []
    for market in event.get("markets") or []:
        if market.get("sportsMarketType") != MONEYLINE_TYPE:
            continue
        if open_only and market.get("closed"):
            continue
        markets.append(market)
    return markets


def _is_two_player_moneyline(raw_market: dict) -> bool:
    labels = _extract_outcome_labels(raw_market)
    if len(labels) != 2:
        return False
    normalized = {label.strip().lower() for label in labels}
    return normalized != {"yes", "no"}


def is_h2h_match_event(event: dict) -> bool:
    """True for vs-style events with one 2-player moneyline (not Yes/No binaries)."""
    title = (event.get("title") or "").strip()
    if not title:
        return False
    lowered = title.lower()
    if "more markets" in lowered or "exact score" in lowered:
        return False
    if " vs " not in lowered and " vs. " not in lowered:
        return False
    moneyline = _moneyline_markets(event, open_only=False)
    if len(moneyline) != 1:
        return False
    return _is_two_player_moneyline(moneyline[0])


def is_h2h_moneyline_submarket(raw_market: dict, event: dict | None = None) -> bool:
    """Binary legs that belong to a composite H2H event — skip standalone import."""
    if raw_market.get("sportsMarketType") != MONEYLINE_TYPE:
        return False
    if event and is_h2h_match_event(event):
        return True
    return _is_two_player_moneyline(raw_market)


def _outcome_probabilities(raw_market: dict) -> dict[str, float]:
    labels = _extract_outcome_labels(raw_market)
    prices = _parse_json_field(raw_market.get("outcomePrices"))
    if len(labels) != 2 or not isinstance(prices, list) or len(prices) != 2:
        return {}
    probs = {}
    for label, price in zip(labels, prices):
        try:
            probs[label] = float(price)
        except (TypeError, ValueError):
            continue
    return probs


def _resolved_outcome_from_moneyline(raw_market: dict) -> str:
    if _market_is_resolved_yes(raw_market):
        labels = _extract_outcome_labels(raw_market)
        for label in labels:
            if str(label).strip().lower() == "yes":
                return str(label)[:255]
        return labels[0][:255] if labels else ""

    labels = _extract_outcome_labels(raw_market)
    prices = _parse_json_field(raw_market.get("outcomePrices"))
    if not isinstance(prices, list) or len(labels) != len(prices):
        return ""
    for label, price in zip(labels, prices):
        try:
            if float(price) >= _RESOLVED_PRICE_THRESHOLD:
                return str(label)[:255]
        except (TypeError, ValueError):
            continue
    return ""


def _match_start_time(event: dict, moneyline_markets: list[dict]):
    for raw_market in moneyline_markets:
        kickoff = _parse_date(raw_market.get("gameStartTime"))
        if kickoff:
            return kickoff
    return _parse_date(event.get("gameStartTime"))


def normalize_h2h_match_event(event: dict, *, default_category: str = "Sports") -> dict | None:
    """Convert a Polymarket H2H event into one internal pick-one market."""
    if not is_h2h_match_event(event):
        return None

    slug = event.get("slug")
    if not slug:
        return None

    moneyline = _moneyline_markets(event, open_only=False)
    if len(moneyline) != 1:
        return None
    raw_market = moneyline[0]

    labels = _extract_outcome_labels(raw_market)
    if len(labels) != 2:
        return None

    outcome_probs = _outcome_probabilities(raw_market)
    if not outcome_probs:
        return None

    parsed_a, parsed_b = parse_match_teams(event.get("title", ""))
    team_a, team_b = labels[0], labels[1]
    if parsed_a and parsed_b:
        for label in labels:
            if parsed_a.lower() in label.lower() or label.lower() in parsed_a.lower():
                team_a = label
            if parsed_b.lower() in label.lower() or label.lower() in parsed_b.lower():
                team_b = label

    resolved_outcome = _resolved_outcome_from_moneyline(raw_market)
    open_markets = _moneyline_markets(event, open_only=True)
    if resolved_outcome:
        status = "resolved"
    elif not open_markets:
        status = "closed"
    else:
        status = "open"

    kickoff = _match_start_time(event, moneyline)
    close_date = _parse_date(raw_market.get("endDate")) or _parse_date(event.get("endDate")) or kickoff
    accepting_orders = _any_accepts_orders(open_markets or moneyline)

    ordered_labels = [team_a, team_b]
    ordered_probs = {label: outcome_probs[label] for label in ordered_labels if label in outcome_probs}

    return {
        "external_id": f"{H2H_MATCH_EXTERNAL_PREFIX}{slug}",
        "title": event.get("title") or f"{team_a} vs. {team_b}",
        "description": event.get("description") or f"Match winner: {team_a} or {team_b}.",
        "category": default_category,
        "source": "polymarket",
        "status": status,
        "outcomes": [{"label": label} for label in ordered_labels],
        "current_probability": ordered_probs,
        "close_date": close_date,
        "resolution_date": close_date if status == "resolved" else None,
        "resolved_outcome": resolved_outcome,
        "accepting_orders": accepting_orders,
        "game_start_time": kickoff,
        "polymarket_slug": slug,
    }


def build_h2h_match_raw(event: dict, *, normalized: dict) -> dict:
    """Composite polymarket_raw payload stored on imported H2H match markets."""
    labels = [item.get("label") for item in normalized.get("outcomes") or [] if item.get("label")]
    team_a = labels[0] if labels else ""
    team_b = labels[1] if len(labels) > 1 else ""
    moneyline = _moneyline_markets(event, open_only=False)
    kickoff = _match_start_time(event, moneyline)
    raw_market = moneyline[0] if moneyline else {}
    labels = _extract_outcome_labels(raw_market)
    token_ids = _parse_json_field(raw_market.get("clobTokenIds")) or []
    outcome_markets = {}
    for index, label in enumerate(labels):
        token_id = str(token_ids[index]) if index < len(token_ids) else ""
        outcome_markets[label] = {
            "id": raw_market.get("id"),
            "conditionId": raw_market.get("conditionId"),
            "slug": raw_market.get("slug"),
            "yes_token_id": token_id or _yes_token_id(raw_market),
        }

    chart_outcomes = []
    probs = normalized.get("current_probability") or {}
    for label in (team_a, team_b):
        if not label:
            continue
        meta = outcome_markets.get(label) or {}
        token_id = meta.get("yes_token_id") or ""
        if not token_id:
            continue
        try:
            probability = float(probs.get(label, 0))
        except (TypeError, ValueError):
            probability = 0.0
        chart_outcomes.append(
            {
                "label": label,
                "probability": probability,
                "slug": meta.get("slug") or "",
                "yes_token_id": token_id,
            }
        )

    return {
        "market_kind": H2H_MATCH_KIND,
        "event_slug": event.get("slug"),
        "kickoff_at": kickoff.isoformat() if kickoff else None,
        "team_a": team_a,
        "team_b": team_b,
        "moneyline_market_id": raw_market.get("id"),
        "outcome_markets": outcome_markets,
        "chart_outcomes": chart_outcomes,
        "volume24hr": event.get("volume24hr") or event.get("volume"),
        "image": event.get("image") or event.get("icon"),
        "icon": event.get("icon") or event.get("image"),
    }
