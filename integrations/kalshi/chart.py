"""Build chart payloads for embedded Kalshi market charts."""

import logging
from datetime import datetime, timedelta, timezone as dt_timezone

from django.utils import timezone

from integrations.kalshi.client import KalshiClient
from integrations.kalshi.urls import get_kalshi_series_ticker, resolve_kalshi_market_url

logger = logging.getLogger(__name__)


def build_kalshi_chart_payload(market, *, trade_limit=200):
    """Return chart series data for a Kalshi market (for client-side Chart.js)."""
    if market.source != market.Source.KALSHI:
        return None

    ticker = market.kalshi_ticker or market.external_id
    series_ticker = get_kalshi_series_ticker(market)
    if not ticker or not series_ticker:
        return None

    yes_label = market.outcome_labels[0] if market.outcome_labels else "Yes"
    current_prob = _current_yes_percent(market)

    points = _fetch_chart_points(series_ticker, ticker, market, trade_limit=trade_limit)
    if not points and current_prob is not None:
        points = [{"ts": timezone.now(), "value": current_prob}]

    if not points:
        return None

    labels = [_format_chart_label(point["ts"]) for point in points]
    values = [point["value"] for point in points]

    return {
        "labels": labels,
        "values": values,
        "yes_label": yes_label,
        "current_percent": values[-1] if values else current_prob,
        "volume_label": market.volume_label,
        "ticker": ticker,
    }


def _fetch_chart_points(series_ticker, ticker, market, *, trade_limit):
    client = KalshiClient()
    now = timezone.now()
    start = market.created_at or (now - timedelta(days=30))
    start_ts = int(start.timestamp())
    end_ts = int(now.timestamp())

    try:
        candlesticks = client.fetch_candlesticks(
            series_ticker,
            ticker,
            start_ts=start_ts,
            end_ts=end_ts,
            period_interval=60,
        )
        points = _normalize_candlesticks(candlesticks)
        if points:
            return points
    except Exception:
        logger.exception("Failed to fetch Kalshi candlesticks for %s", ticker)

    try:
        trades = client.fetch_trades(ticker, limit=trade_limit)
        return _normalize_trades(trades)
    except Exception:
        logger.exception("Failed to fetch Kalshi trades for %s", ticker)
        return []


def _normalize_candlesticks(candlesticks):
    points = []
    for candle in candlesticks or []:
        ts = _parse_ts(candle.get("end_period_ts") or candle.get("ts"))
        value = _parse_price(
            candle.get("close_dollars")
            or candle.get("close")
            or candle.get("price_dollars")
        )
        if ts is None or value is None:
            continue
        points.append({"ts": ts, "value": value})
    points.sort(key=lambda item: item["ts"])
    return _dedupe_points(points)


def _normalize_trades(trades):
    points = []
    for trade in trades or []:
        ts = _parse_ts(trade.get("created_time"))
        value = _parse_price(trade.get("yes_price_dollars"))
        if ts is None or value is None:
            continue
        points.append({"ts": ts, "value": value})
    points.sort(key=lambda item: item["ts"])
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


def _current_yes_percent(market):
    labels = market.outcome_labels
    if not labels:
        return None
    yes_label = labels[0]
    prob = (market.current_probability or {}).get(yes_label)
    if prob is None:
        return None
    try:
        value = float(prob)
    except (TypeError, ValueError):
        return None
    return round(value * 100 if value <= 1 else value, 2)


def _parse_price(value):
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return round(parsed * 100 if parsed <= 1 else parsed, 2)


def _parse_ts(value):
    if not value:
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


def _format_chart_label(dt):
    return timezone.localtime(dt).strftime("%b %d %H:%M")
