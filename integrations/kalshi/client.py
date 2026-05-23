"""Kalshi API client — read-only market import (no trading)."""

import logging
import time
from datetime import datetime

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)

KALSHI_STATUS_OPEN = "open"
KALSHI_STATUS_SETTLED = "settled"


class KalshiRateLimitError(requests.HTTPError):
    """Kalshi API returned 429 after retries were exhausted."""


class KalshiClient:
    def __init__(self, base_url=None):
        self.base_url = (base_url or settings.KALSHI_API_URL).rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        self._last_request_at = 0.0

    def _throttle(self):
        min_interval = getattr(settings, "KALSHI_API_MIN_INTERVAL_MS", 300) / 1000.0
        if min_interval <= 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)

    def _get(self, url, *, params=None, not_found_ok=False):
        max_retries = getattr(settings, "KALSHI_API_MAX_RETRIES", 3)
        last_response = None

        for attempt in range(max_retries + 1):
            self._throttle()
            response = self.session.get(url, params=params, timeout=30)
            self._last_request_at = time.monotonic()
            last_response = response

            if response.status_code == 404 and not_found_ok:
                return None

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                try:
                    wait_seconds = max(float(retry_after), 1.0)
                except (TypeError, ValueError):
                    wait_seconds = min(2 ** attempt, 8)
                logger.warning(
                    "Kalshi rate limited (429) on %s — retry %s/%s in %.1fs",
                    url,
                    attempt + 1,
                    max_retries,
                    wait_seconds,
                )
                if attempt >= max_retries:
                    break
                time.sleep(wait_seconds)
                continue

            response.raise_for_status()
            return response

        if last_response is not None and last_response.status_code == 429:
            raise KalshiRateLimitError(
                f"Kalshi rate limit exceeded for {url}",
                response=last_response,
            )
        if last_response is not None:
            last_response.raise_for_status()
        raise requests.RequestException(f"Kalshi request failed for {url}")

    def fetch_markets(
        self,
        *,
        limit=100,
        cursor=None,
        status=KALSHI_STATUS_OPEN,
        series_ticker=None,
        event_ticker=None,
        exclude_mve=True,
    ):
        params = {"limit": min(max(limit, 1), 1000)}
        if cursor:
            params["cursor"] = cursor
        if status:
            params["status"] = status
        if series_ticker:
            params["series_ticker"] = series_ticker
        if event_ticker:
            params["event_ticker"] = event_ticker
        if exclude_mve:
            params["mve_filter"] = "exclude"

        url = f"{self.base_url}/markets"
        response = self._get(url, params=params)
        data = response.json()
        return data.get("markets", []), data.get("cursor", "")

    def fetch_all_markets(self, *, max_pages=10, **kwargs):
        """Paginate through Kalshi markets up to max_pages."""
        markets = []
        cursor = None

        for _ in range(max_pages):
            page, cursor = self.fetch_markets(cursor=cursor, **kwargs)
            markets.extend(page)
            if not cursor or not page:
                break

        return markets

    def fetch_market_by_ticker(self, ticker):
        url = f"{self.base_url}/markets/{ticker}"
        response = self._get(url)
        payload = response.json()
        return payload.get("market", payload)

    def fetch_event_by_ticker(self, event_ticker):
        url = f"{self.base_url}/events/{event_ticker}"
        response = self._get(url, not_found_ok=True)
        if response is None:
            return None
        return response.json()

    def fetch_event_metadata(self, event_ticker):
        url = f"{self.base_url}/events/{event_ticker}/metadata"
        response = self._get(url, not_found_ok=True)
        if response is None:
            return None
        return response.json()

    def fetch_candlesticks(
        self,
        series_ticker,
        market_ticker,
        *,
        start_ts,
        end_ts,
        period_interval=60,
    ):
        url = f"{self.base_url}/series/{series_ticker}/markets/{market_ticker}/candlesticks"
        params = {
            "start_ts": int(start_ts),
            "end_ts": int(end_ts),
            "period_interval": period_interval,
            "include_latest_before_start": "true",
        }
        response = self._get(url, params=params)
        return response.json().get("candlesticks", [])

    def fetch_trades(self, ticker, *, limit=200):
        url = f"{self.base_url}/markets/trades"
        params = {"ticker": ticker, "limit": min(max(limit, 1), 1000)}
        response = self._get(url, params=params)
        return response.json().get("trades", [])


def is_binary_kalshi_market(raw):
    return raw.get("market_type") == "binary"


def _resolve_kalshi_outcome_labels(raw):
    """Build distinct Yes/No labels; Kalshi threshold markets often duplicate sub_titles."""
    yes_label = (raw.get("yes_sub_title") or "Yes").strip()
    no_label = (raw.get("no_sub_title") or "No").strip()

    if yes_label.casefold() != no_label.casefold():
        return yes_label[:255], no_label[:255]

    threshold = yes_label or (raw.get("subtitle") or "").strip()
    if not threshold:
        return "Yes", "No"

    lower = threshold.lower()
    if lower.startswith("above "):
        return threshold[:255], f"At or below {threshold[6:].strip()}"[:255]
    if lower.startswith("below "):
        return threshold[:255], f"At or above {threshold[6:].strip()}"[:255]
    if lower.startswith("at least "):
        return threshold[:255], f"Fewer than {threshold[9:].strip()}"[:255]
    if lower.startswith("over "):
        return threshold[:255], f"At or below {threshold[5:].strip()}"[:255]
    if lower.startswith("under "):
        return threshold[:255], f"At or above {threshold[6:].strip()}"[:255]

    return "Yes", "No"


def normalize_kalshi_record(raw, *, default_category="", raw_event=None):
    """Convert a Kalshi API market record into internal market dict."""
    ticker = raw.get("ticker") or ""
    if not ticker:
        raise ValueError("Kalshi record missing ticker")

    title = raw.get("title") or "Untitled Market"
    description_parts = [
        raw.get("rules_primary") or "",
        raw.get("rules_secondary") or "",
    ]
    description = "\n\n".join(part.strip() for part in description_parts if part and part.strip())

    yes_label, no_label = _resolve_kalshi_outcome_labels(raw)
    outcomes = [{"label": yes_label}, {"label": no_label}]

    yes_price = _parse_dollar_price(raw.get("last_price_dollars"))
    if yes_price in (None, 0.0):
        yes_price = _mid_price(raw.get("yes_bid_dollars"), raw.get("yes_ask_dollars"))
    no_price = _parse_dollar_price(
        None,
        fallback=round(1.0 - yes_price, 4) if yes_price is not None else None,
    )
    probabilities = {}
    if yes_price is not None:
        probabilities[yes_label] = yes_price
    if no_price is not None:
        probabilities[no_label] = no_price

    status = _map_kalshi_status(raw.get("status", ""))
    resolved_outcome = _map_kalshi_result(raw.get("result"), yes_label=yes_label, no_label=no_label)

    close_date = _parse_date(
        raw.get("close_time") or raw.get("latest_expiration_time") or raw.get("expiration_time")
    )
    resolution_date = _parse_date(raw.get("settlement_ts")) if status == "resolved" else None

    category = default_category
    if raw_event and isinstance(raw_event, dict):
        event = raw_event.get("event") or raw_event
        category = event.get("category") or category

    return {
        "external_id": ticker,
        "title": title[:500],
        "description": description,
        "category": str(category)[:100],
        "source": "kalshi",
        "status": status,
        "outcomes": outcomes,
        "current_probability": probabilities,
        "close_date": close_date,
        "resolution_date": resolution_date,
        "resolved_outcome": str(resolved_outcome)[:255],
        "kalshi_ticker": ticker[:255],
    }


def _map_kalshi_status(kalshi_status):
    normalized = (kalshi_status or "").lower()
    if normalized in {"finalized", "determined", "settled"}:
        return "resolved"
    if normalized in {"closed", "inactive"}:
        return "closed"
    return "open"


def _map_kalshi_result(result, *, yes_label="Yes", no_label="No"):
    normalized = (result or "").lower()
    if normalized == "yes":
        return yes_label
    if normalized == "no":
        return no_label
    return ""


def _parse_dollar_price(value, *, fallback=None):
    for candidate in (value, fallback):
        if candidate in (None, ""):
            continue
        try:
            return float(candidate)
        except (TypeError, ValueError):
            continue
    return None


def _mid_price(bid, ask):
    bid_price = _parse_dollar_price(bid)
    ask_price = _parse_dollar_price(ask)
    if bid_price is not None and ask_price is not None:
        return round((bid_price + ask_price) / 2, 4)
    if bid_price is not None:
        return bid_price
    if ask_price is not None:
        return ask_price
    return None


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
