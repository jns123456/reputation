"""Polymarket soccer match markets — merge 3-way moneyline into one forecast market."""

import logging
import re

from integrations.polymarket.client import (
    _any_accepts_orders,
    _market_is_resolved_yes,
    _parse_date,
    _parse_json_field,
    _yes_token_id,
)

logger = logging.getLogger(__name__)

WORLD_CUP_MATCH_EXTERNAL_PREFIX = "wc-match:"
DRAW_OUTCOME_LABEL = "Draw"
MONEYLINE_TYPE = "moneyline"
WORLD_CUP_TAG_SLUGS = ("fifa-world-cup", "2026-fifa-world-cup")
# Group-stage match events (3-way moneyline) live under this tag on Polymarket.
WORLD_CUP_MATCH_TAG_SLUG = "fifa-world-cup"
# Polymarket tags that carry 3-way soccer moneyline events (friendlies, leagues, etc.).
SOCCER_MATCH_TAG_SLUGS = (
    "fifa-world-cup",
    "2026-fifa-world-cup",
    "fifa-friendlies",
    "soccer",
    "mls",
    "la-liga",
    "epl",
    "ucl",
)


def is_world_cup_match_market(market) -> bool:
    external_id = getattr(market, "external_id", "") or ""
    if external_id.startswith(WORLD_CUP_MATCH_EXTERNAL_PREFIX):
        return True
    raw = getattr(market, "polymarket_raw", None) or {}
    return raw.get("market_kind") == "soccer_match_3way"


def is_soccer_match_event(event: dict) -> bool:
    title = (event.get("title") or "").strip()
    if not title:
        return False
    lowered = title.lower()
    if "more markets" in lowered or "exact score" in lowered:
        return False
    if " vs " not in lowered and " vs. " not in lowered:
        return False
    # Count all moneyline legs, not only open ones. After a match ends every leg is
    # closed; requiring open legs made refresh/normalize return None and left forecasts
    # stuck pending while Polymarket already showed the winner.
    return len(_moneyline_markets(event, open_only=False)) == 3


# Backwards-compatible alias — detection is not World-Cup-specific.
is_world_cup_match_event = is_soccer_match_event


def is_soccer_moneyline_submarket(raw_market: dict, event: dict | None = None) -> bool:
    """True for binary Yes/No legs of a grouped 3-way soccer moneyline event."""
    if raw_market.get("sportsMarketType") != MONEYLINE_TYPE:
        return False
    if event and is_soccer_match_event(event):
        return True
    return False


def parse_match_teams(title: str) -> tuple[str | None, str | None]:
    parts = re.split(r"\s+vs\.?\s+", title.strip(), maxsplit=1, flags=re.IGNORECASE)
    if len(parts) != 2:
        return None, None
    return parts[0].strip(), parts[1].strip()


def _normalize_team_name_for_match(name: str) -> str:
    """Collapse hyphens, ``and``, and spacing so title vs question variants still match."""
    lowered = name.lower().strip()
    lowered = re.sub(r"\s+and\s+", " ", lowered)
    lowered = lowered.replace("-", " ")
    return re.sub(r"\s+", " ", lowered).strip()


def _team_name_in_question(team: str, question_lower: str) -> bool:
    if team.lower() in question_lower:
        return True
    normalized_team = _normalize_team_name_for_match(team)
    normalized_question = _normalize_team_name_for_match(question_lower)
    return bool(normalized_team and normalized_team in normalized_question)


def classify_moneyline_outcome(question: str, team_a: str, team_b: str) -> str | None:
    question_lower = question.lower()
    if "draw" in question_lower:
        return DRAW_OUTCOME_LABEL
    if "win" not in question_lower:
        return None
    for team in (team_a, team_b):
        if _team_name_in_question(team, question_lower):
            return team
    return None


def _moneyline_markets(event: dict, *, open_only: bool) -> list[dict]:
    markets = []
    for market in event.get("markets") or []:
        if market.get("sportsMarketType") != MONEYLINE_TYPE:
            continue
        if open_only and market.get("closed"):
            continue
        markets.append(market)
    return markets


def _yes_price(raw_market: dict) -> float | None:
    prices = _parse_json_field(raw_market.get("outcomePrices"))
    if not isinstance(prices, list) or not prices:
        return None
    try:
        return float(prices[0])
    except (TypeError, ValueError):
        return None


def _match_kickoff_time(event: dict, moneyline_markets: list[dict]):
    """Return the scheduled kickoff, not the market listing/open timestamp.

    Sports events from Polymarket often use ``startDate`` for when the market was
    listed. The actual match kickoff is carried by ``gameStartTime`` on the
    event or its sports sub-markets.
    """
    for raw_market in moneyline_markets:
        kickoff = _parse_date(raw_market.get("gameStartTime"))
        if kickoff:
            return kickoff
    return _parse_date(event.get("gameStartTime"))


def normalize_soccer_match_event(event: dict, *, default_category: str = "Sports") -> dict | None:
    """Convert a Polymarket match event into a single 3-outcome market dict."""
    if not is_soccer_match_event(event):
        return None

    slug = event.get("slug")
    if not slug:
        return None

    team_a, team_b = parse_match_teams(event.get("title", ""))
    if not team_a or not team_b:
        return None

    moneyline = _moneyline_markets(event, open_only=False)
    if len(moneyline) != 3:
        return None

    outcome_probs: dict[str, float] = {}
    moneyline_markets: dict[str, dict] = {}
    resolved_outcome = ""
    open_count = 0

    for raw_market in moneyline:
        label = classify_moneyline_outcome(raw_market.get("question") or "", team_a, team_b)
        if not label:
            logger.warning("Could not classify moneyline market: %s", raw_market.get("question"))
            return None

        yes_price = _yes_price(raw_market)
        if yes_price is not None:
            outcome_probs[label] = yes_price

        moneyline_markets[label] = {
            "id": raw_market.get("id"),
            "conditionId": raw_market.get("conditionId"),
            "slug": raw_market.get("slug"),
        }

        if _market_is_resolved_yes(raw_market):
            resolved_outcome = label
        if not raw_market.get("closed"):
            open_count += 1

    if resolved_outcome:
        status = "resolved"
    elif open_count == 0:
        status = "closed"
    else:
        status = "open"

    ordered_labels = [team_a, DRAW_OUTCOME_LABEL, team_b]
    ordered_probs = {
        label: outcome_probs[label]
        for label in ordered_labels
        if label in outcome_probs
    }

    kickoff = _match_kickoff_time(event, moneyline)
    close_date = _parse_date(event.get("endDate")) or kickoff
    open_moneyline = [m for m in moneyline if not m.get("closed")]
    accepting_orders = _any_accepts_orders(open_moneyline)

    return {
        "external_id": f"{WORLD_CUP_MATCH_EXTERNAL_PREFIX}{slug}",
        "title": event.get("title") or f"{team_a} vs. {team_b}",
        "description": (
            event.get("description")
            or f"Full-time result: {team_a}, {DRAW_OUTCOME_LABEL}, or {team_b}."
        ),
        "category": default_category,
        "source": "polymarket",
        "status": status,
        "outcomes": [{"label": label} for label in ordered_labels],
        "current_probability": ordered_probs,
        "close_date": close_date or kickoff,
        "resolution_date": close_date if status == "resolved" else None,
        "resolved_outcome": resolved_outcome,
        "accepting_orders": accepting_orders,
        "game_start_time": kickoff,
        "polymarket_slug": slug,
    }


normalize_world_cup_match_event = normalize_soccer_match_event


def build_soccer_match_raw(event: dict, *, normalized: dict) -> dict:
    """Composite polymarket_raw payload stored on imported match markets."""
    team_a, team_b = parse_match_teams(event.get("title", ""))
    moneyline = _moneyline_markets(event, open_only=False)
    kickoff = _match_kickoff_time(event, moneyline)
    moneyline_markets = {}
    for raw_market in moneyline:
        label = classify_moneyline_outcome(raw_market.get("question") or "", team_a or "", team_b or "")
        if not label:
            continue
        moneyline_markets[label] = {
            "id": raw_market.get("id"),
            "conditionId": raw_market.get("conditionId"),
            "slug": raw_market.get("slug"),
            "yes_token_id": _yes_token_id(raw_market),
        }

    chart_outcomes = []
    probs = normalized.get("current_probability") or {}
    for label in (team_a, team_b):
        if not label:
            continue
        meta = moneyline_markets.get(label) or {}
        yes_token_id = meta.get("yes_token_id") or ""
        if not yes_token_id:
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
                "yes_token_id": yes_token_id,
            }
        )

    return {
        "market_kind": "soccer_match_3way",
        "event_slug": event.get("slug"),
        "kickoff_at": kickoff.isoformat() if kickoff else None,
        "team_a": team_a,
        "team_b": team_b,
        "moneyline_markets": moneyline_markets,
        "chart_outcomes": chart_outcomes,
        "volume24hr": event.get("volume24hr") or event.get("volume"),
        "image": event.get("image") or event.get("icon"),
        "icon": event.get("icon") or event.get("image"),
    }


build_world_cup_match_raw = build_soccer_match_raw


def ordered_soccer_probability_items(market) -> list[tuple[str, float]]:
    """Return (label, probability) pairs in home → draw → away order."""
    probs = getattr(market, "current_probability", None) or {}
    if not probs:
        return []

    team_a = getattr(market, "match_team_a", "") or ""
    team_b = getattr(market, "match_team_b", "") or ""
    if team_a and team_b:
        labels = [team_a, DRAW_OUTCOME_LABEL, team_b]
    else:
        labels = getattr(market, "outcome_labels", None) or list(probs.keys())

    return [(label, probs[label]) for label in labels if label in probs]
