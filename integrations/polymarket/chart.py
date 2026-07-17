"""Build multi-outcome chart payloads from Polymarket CLOB price history."""

import logging
import time
from datetime import datetime, timezone as dt_timezone

import requests
from django.utils import timezone

from integrations.polymarket.constants import (
    MULTI_OUTCOME_CHART_OUTCOMES,
    POLYMARKET_EVENT_EXTERNAL_PREFIX,
)
from integrations.polymarket.client import (
    PolymarketClient,
    build_polymarket_event_raw,
    is_multi_outcome_event_market,
    normalize_polymarket_event_record,
    select_top_chart_outcomes,
)
from integrations.services import _log_polymarket_fetch_failure

logger = logging.getLogger(__name__)

_TRANSIENT_REQUEST_ERRORS = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    requests.exceptions.ChunkedEncodingError,
)

CLOB_API_URL = "https://clob.polymarket.com"
CHART_COLORS = [
    "rgb(59 130 246)",
    "rgb(16 185 129)",
    "rgb(245 158 11)",
    "rgb(244 63 94)",
]
CHART_FILL_COLORS = [
    "rgba(59, 130, 246, 0.08)",
    "rgba(16, 185, 129, 0.08)",
    "rgba(245, 158, 11, 0.08)",
    "rgba(244, 63, 94, 0.08)",
]
SOCCER_CHART_COLORS = [
    "rgb(16 185 129)",
    "rgb(244 63 94)",
]
SOCCER_CHART_FILL_COLORS = [
    "rgba(16, 185, 129, 0.08)",
    "rgba(244, 63, 94, 0.08)",
]


def build_polymarket_soccer_match_chart_payload(
    market,
    *,
    interval="max",
    fidelity=1440,
):
    """Return home/away price history for soccer matches (draw excluded)."""
    from integrations.polymarket.soccer_matches import (
        DRAW_OUTCOME_LABEL,
        is_world_cup_match_market,
    )

    if not is_world_cup_match_market(market):
        return None

    chart_outcomes = _select_soccer_chart_outcomes(market)
    if len(chart_outcomes) < 2:
        return None

    series = []
    for index, outcome in enumerate(chart_outcomes):
        label = outcome.get("label") or "Outcome"
        if label == DRAW_OUTCOME_LABEL:
            continue
        token_id = outcome.get("yes_token_id")
        if not token_id:
            continue

        points = _fetch_price_points(token_id, interval=interval, fidelity=fidelity)
        current_percent = _current_percent(outcome.get("probability"), points)
        if not points and current_percent is None:
            continue
        if not points and current_percent is not None:
            points = [{"ts": timezone.now(), "value": current_percent}]

        series.append(
            {
                "label": label,
                "color": SOCCER_CHART_COLORS[index % len(SOCCER_CHART_COLORS)],
                "fill_color": SOCCER_CHART_FILL_COLORS[index % len(SOCCER_CHART_FILL_COLORS)],
                "current_percent": current_percent,
                "points": [
                    {
                        "ts": point["ts"].isoformat(),
                        "value": point["value"],
                    }
                    for point in points
                ],
            }
        )

    if len(series) < 2:
        return None

    return {
        "series": series,
        "volume_label": _volume_label(market),
    }


def build_polymarket_multi_outcome_chart_payload(
    market,
    *,
    limit=MULTI_OUTCOME_CHART_OUTCOMES,
    interval="max",
    fidelity=1440,
):
    """Return chart series for the top-N outcomes by Yes probability."""
    if not is_multi_outcome_event_market(market):
        return None

    chart_outcomes = _select_chart_outcomes(market, limit=limit)
    if not chart_outcomes:
        return None

    series = []
    for index, outcome in enumerate(chart_outcomes):
        token_id = outcome.get("yes_token_id")
        label = outcome.get("label") or "Outcome"
        if not token_id:
            continue

        points = _fetch_price_points(token_id, interval=interval, fidelity=fidelity)
        current_percent = _current_percent(outcome.get("probability"), points)
        if not points and current_percent is None:
            continue
        if not points and current_percent is not None:
            points = [{"ts": timezone.now(), "value": current_percent}]

        series.append(
            {
                "label": label,
                "color": CHART_COLORS[index % len(CHART_COLORS)],
                "fill_color": CHART_FILL_COLORS[index % len(CHART_FILL_COLORS)],
                "current_percent": current_percent,
                "points": [
                    {
                        "ts": point["ts"].isoformat(),
                        "value": point["value"],
                    }
                    for point in points
                ],
            }
        )

    if not series:
        return None

    return {
        "series": series,
        "volume_label": _volume_label(market),
    }


def _select_soccer_chart_outcomes(market) -> list[dict]:
    """Home and away moneyline legs only — Polymarket sports charts omit draw."""
    from integrations.polymarket.soccer_matches import (
        DRAW_OUTCOME_LABEL,
        build_soccer_match_raw,
        normalize_soccer_match_event,
    )

    raw = market.polymarket_raw or {}
    stored = [
        item
        for item in (raw.get("chart_outcomes") or [])
        if (item.get("label") or "") != DRAW_OUTCOME_LABEL
    ]
    if len(stored) >= 2:
        return stored[:2]

    team_a = raw.get("team_a") or market.match_team_a
    team_b = raw.get("team_b") or market.match_team_b
    moneyline = raw.get("moneyline_markets") or {}
    probs = market.current_probability or {}
    outcomes = []
    for label in (team_a, team_b):
        if not label:
            continue
        meta = moneyline.get(label) or {}
        yes_token_id = meta.get("yes_token_id") or ""
        if not yes_token_id:
            continue
        try:
            probability = float(probs.get(label, 0))
        except (TypeError, ValueError):
            probability = 0.0
        outcomes.append(
            {
                "label": label,
                "probability": probability,
                "slug": meta.get("slug") or "",
                "yes_token_id": yes_token_id,
            }
        )
    if len(outcomes) >= 2:
        return outcomes

    slug = _event_slug_for_market(market)
    if not slug:
        return []

    try:
        event = PolymarketClient().fetch_event_by_slug(slug)
    except Exception as exc:
        _log_polymarket_fetch_failure(
            exc,
            "Failed to fetch Polymarket event for soccer match chart: %s",
            slug,
        )
        return []

    if not event:
        return []

    normalized = normalize_soccer_match_event(
        event,
        default_category=market.category or "",
    )
    if not normalized:
        return []

    raw_payload = build_soccer_match_raw(event, normalized=normalized)
    chart_outcomes = raw_payload.get("chart_outcomes") or []
    if chart_outcomes:
        _persist_soccer_chart_backfill(market, normalized=normalized, raw=raw_payload, event=event)
    return chart_outcomes[:2]


def _persist_soccer_chart_backfill(market, *, normalized, raw, event):
    """Store token metadata for soccer match charts on older imports."""
    try:
        market.polymarket_raw = {**(market.polymarket_raw or {}), **raw}
        market.polymarket_event_raw = event
        market.current_probability = normalized.get("current_probability") or market.current_probability
        market.outcomes = normalized.get("outcomes") or market.outcomes
        market.volume_total = _parse_float(raw.get("volume24hr"), market.volume_total)
        market.volume_24h = _parse_float(raw.get("volume24hr"), market.volume_24h)
        market.polymarket_synced_at = timezone.now()
        market.save(
            update_fields=[
                "polymarket_raw",
                "polymarket_event_raw",
                "current_probability",
                "outcomes",
                "volume_total",
                "volume_24h",
                "polymarket_synced_at",
                "updated_at",
            ]
        )
    except Exception:
        logger.exception("Failed to persist Polymarket soccer chart backfill for %s", market.external_id)


def _select_chart_outcomes(market, *, limit):
    chart_outcomes = select_top_chart_outcomes(market, limit=limit)
    expected_count = min(limit, len(getattr(market, "outcome_labels", []) or []) or limit)
    if chart_outcomes and len(chart_outcomes) >= expected_count:
        return chart_outcomes

    slug = _event_slug_for_market(market)
    if not slug:
        return []

    try:
        event = PolymarketClient().fetch_event_by_slug(slug)
    except Exception as exc:
        _log_polymarket_fetch_failure(
            exc,
            "Failed to fetch Polymarket event for multi-outcome chart: %s",
            slug,
        )
        return []

    if not event:
        return []

    normalized = normalize_polymarket_event_record(
        event,
        default_category=market.category or "",
        require_open=False,
    )
    if not normalized:
        return []

    raw = build_polymarket_event_raw(event, normalized=normalized)
    chart_outcomes = (raw.get("chart_outcomes") or [])[:limit]
    if chart_outcomes:
        _persist_chart_backfill(market, normalized=normalized, raw=raw, event=event)
    return chart_outcomes


def _event_slug_for_market(market):
    raw = market.polymarket_raw or {}
    slug = market.polymarket_slug or raw.get("event_slug") or raw.get("slug")
    if slug:
        return slug
    external_id = market.external_id or ""
    if external_id.startswith(POLYMARKET_EVENT_EXTERNAL_PREFIX):
        return external_id.removeprefix(POLYMARKET_EVENT_EXTERNAL_PREFIX)
    return ""


def _persist_chart_backfill(market, *, normalized, raw, event):
    """Store token metadata so older imported events stop falling back to iframe embeds."""
    try:
        market.polymarket_raw = {**(market.polymarket_raw or {}), **raw}
        market.polymarket_event_raw = event
        market.current_probability = normalized.get("current_probability") or market.current_probability
        market.outcomes = normalized.get("outcomes") or market.outcomes
        market.volume_total = _parse_float(raw.get("volumeNum") or raw.get("volume"), market.volume_total)
        market.volume_24h = _parse_float(raw.get("volume24hr"), market.volume_24h)
        market.polymarket_synced_at = timezone.now()
        market.save(
            update_fields=[
                "polymarket_raw",
                "polymarket_event_raw",
                "current_probability",
                "outcomes",
                "volume_total",
                "volume_24h",
                "polymarket_synced_at",
                "updated_at",
            ]
        )
    except Exception:
        logger.exception("Failed to persist Polymarket chart backfill for %s", market.external_id)


def _get_price_history_with_retry(token_id, *, interval, fidelity, max_attempts=3):
    """GET CLOB price history with short backoff on transient Polymarket failures."""
    url = f"{CLOB_API_URL}/prices-history"
    params = {
        "market": token_id,
        "interval": interval,
        "fidelity": fidelity,
    }
    last_exc = None
    for attempt in range(max_attempts):
        try:
            response = requests.get(
                url,
                params=params,
                timeout=20,
                headers={"Accept": "application/json"},
            )
        except _TRANSIENT_REQUEST_ERRORS as exc:
            last_exc = exc
            if attempt + 1 >= max_attempts:
                raise
            time.sleep(2**attempt)
            continue
        if response.status_code < 500:
            return response
        if attempt + 1 >= max_attempts:
            return response
        time.sleep(2**attempt)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("unreachable")


def _fetch_price_points(token_id, *, interval, fidelity):
    try:
        response = _get_price_history_with_retry(
            token_id,
            interval=interval,
            fidelity=fidelity,
        )
        if response.status_code >= 500:
            logger.warning(
                "Failed to fetch Polymarket price history for %s (HTTP %s)",
                token_id,
                response.status_code,
            )
            return []
        response.raise_for_status()
        history = response.json().get("history") or []
    except Exception as exc:
        _log_polymarket_fetch_failure(
            exc,
            "Failed to fetch Polymarket price history for %s",
            token_id,
        )
        return []

    points = []
    for item in history:
        ts = _parse_ts(item.get("t"))
        value = _parse_price(item.get("p"))
        if ts is None or value is None:
            continue
        points.append({"ts": ts, "value": value})
    points.sort(key=lambda point: point["ts"])
    return _dedupe_points(points)


def _dedupe_points(points):
    if not points:
        return points
    deduped = [points[0]]
    for point in points[1:]:
        if point["ts"] == deduped[-1]["ts"]:
            deduped[-1] = point
        else:
            deduped.append(point)
    return deduped


def _current_percent(probability, points):
    if points:
        return points[-1]["value"]
    try:
        value = float(probability)
    except (TypeError, ValueError):
        return None
    return round(value * 100 if value <= 1 else value, 2)


def _parse_float(value, default):
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_price(value):
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return round(parsed * 100 if parsed <= 1 else parsed, 2)


def _parse_ts(value):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=dt_timezone.utc)
    from django.utils.dateparse import parse_datetime

    dt = parse_datetime(str(value))
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, dt_timezone.utc)
    return dt


def _volume_label(market):
    raw = market.polymarket_raw or {}
    volume = raw.get("volumeNum") or raw.get("volume") or market.volume_total
    if volume in (None, ""):
        return ""
    try:
        amount = float(volume)
    except (TypeError, ValueError):
        return ""
    if amount >= 1_000_000_000:
        return f"${amount / 1_000_000_000:.1f}b Vol."
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.1f}m Vol."
    if amount >= 1_000:
        return f"${amount / 1_000:.1f}k Vol."
    return f"${amount:,.0f} Vol."
