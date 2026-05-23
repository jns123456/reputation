"""Format Polymarket API payloads for template display."""

import json
from datetime import datetime

from integrations.polymarket.client import _parse_json_field

# Field groupings for readable UI sections
MARKET_FIELD_GROUPS = {
    "Identity": [
        "id", "question", "conditionId", "slug", "questionID", "category",
        "groupItemTitle", "groupItemThreshold", "marketType",
    ],
    "Outcomes & pricing": [
        "outcomes", "outcomePrices", "tokens", "lastTradePrice", "bestBid", "bestAsk",
        "spread", "oneHourPriceChange", "oneDayPriceChange", "oneWeekPriceChange",
        "oneMonthPriceChange",
    ],
    "Volume & liquidity": [
        "volume", "volumeNum", "volume24hr", "volume1wk", "volume1mo", "volume1yr",
        "volumeClob", "volume24hrClob", "volume1wkClob", "volume1moClob", "volume1yrClob",
        "liquidity", "liquidityNum", "liquidityClob", "openInterest", "competitive",
    ],
    "Dates": [
        "startDate", "startDateIso", "endDate", "endDateIso", "closeTime",
        "createdAt", "updatedAt", "acceptingOrdersTimestamp", "deployingTimestamp",
    ],
    "Resolution": [
        "resolutionSource", "resolvedOutcome", "resolved", "automaticallyResolved",
        "resolvedBy", "umaResolutionStatuses", "winning_outcome",
    ],
    "Order book & trading": [
        "enableOrderBook", "acceptingOrders", "orderPriceMinTickSize", "orderMinSize",
        "clobTokenIds", "negRisk", "negRiskRequestID", "negRiskOther", "rfqEnabled",
        "feesEnabled", "feeType", "makerBaseFee", "takerBaseFee",
    ],
    "Rewards": [
        "clobRewards", "rewardsMinSize", "rewardsMaxSpread", "umaBond", "umaReward",
        "holdingRewardsEnabled",
    ],
    "Media & links": ["image", "icon", "description"],
    "Flags & status": [
        "active", "closed", "archived", "new", "featured", "restricted", "approved",
        "ready", "funded", "cyom", "automaticallyActive", "clearBookOnStart",
        "manualActivation", "pendingDeployment", "deploying", "hasReviewedDates",
        "requiresTranslation", "pagerDutyNotificationEnabled", "customLiveness",
    ],
    "On-chain & metadata": [
        "marketMakerAddress", "submitted_by", "events", "tags",
    ],
}

EVENT_FIELD_GROUPS = {
    "Event identity": ["id", "ticker", "slug", "title", "category"],
    "Event volume": [
        "volume", "volume24hr", "volume1wk", "volume1mo", "volume1yr",
        "liquidity", "liquidityClob", "openInterest", "competitive", "commentCount",
    ],
    "Event dates": ["startDate", "creationDate", "endDate", "createdAt", "updatedAt"],
    "Event status": [
        "active", "closed", "archived", "new", "featured", "restricted",
        "enableOrderBook",
    ],
    "Event media": ["image", "icon", "description", "resolutionSource"],
}


def _format_value(value):
    if value is None:
        return "—", "null"
    if isinstance(value, bool):
        return "Yes" if value else "No", "boolean"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and 0 <= value <= 1 and value not in (0, 1):
            return f"{value:.4f} ({value * 100:.1f}%)", "percent"
        return str(value), "number"
    if isinstance(value, str):
        parsed = _parse_json_field(value)
        if parsed is not None and parsed != value:
            return json.dumps(parsed, indent=2, ensure_ascii=False), "json"
        if value.startswith("http://") or value.startswith("https://"):
            return value, "url"
        if len(value) > 200:
            return value, "longtext"
        return value, "text"
    if isinstance(value, (list, dict)):
        return json.dumps(value, indent=2, ensure_ascii=False), "json"
    if isinstance(value, datetime):
        return value.isoformat(), "datetime"
    return str(value), "text"


def _collect_fields(raw, field_groups, *, exclude_keys=None):
    if not raw:
        return []

    exclude_keys = exclude_keys or set()
    assigned = set()
    sections = []

    for section_name, keys in field_groups.items():
        fields = []
        for key in keys:
            if key in raw and key not in exclude_keys:
                display, value_type = _format_value(raw[key])
                fields.append({"key": key, "value": display, "type": value_type})
                assigned.add(key)
        if fields:
            sections.append({"title": section_name, "fields": fields})

    remaining = []
    for key in sorted(raw.keys()):
        if key not in assigned and key not in exclude_keys:
            if key == "markets":
                continue
            display, value_type = _format_value(raw[key])
            remaining.append({"key": key, "value": display, "type": value_type})

    if remaining:
        sections.append({"title": "Other fields", "fields": remaining})

    return sections


def build_polymarket_display_sections(*, market_raw, event_raw=None):
    """Build grouped field sections for market detail template."""
    sections = []
    if market_raw:
        sections.append({
            "title": "Polymarket Market API",
            "subtitle": f"Market ID {market_raw.get('id', '—')}",
            "groups": _collect_fields(market_raw, MARKET_FIELD_GROUPS),
        })
    if event_raw:
        sections.append({
            "title": "Polymarket Event API",
            "subtitle": f"Event ID {event_raw.get('id', '—')}",
            "groups": _collect_fields(
                event_raw,
                EVENT_FIELD_GROUPS,
                exclude_keys={"markets"},
            ),
        })
        nested_markets = event_raw.get("markets") or []
        if nested_markets:
            sections.append({
                "title": "Nested markets in event",
                "subtitle": f"{len(nested_markets)} market(s)",
                "groups": [{
                    "title": "Markets array",
                    "fields": [{
                        "key": f"markets[{i}]",
                        "value": json.dumps(m, indent=2, ensure_ascii=False),
                        "type": "json",
                    } for i, m in enumerate(nested_markets)],
                }],
            })
    return sections


def build_prediction_snapshot_sections(prediction):
    """Display all stored prediction data including Polymarket probability snapshot."""
    fields = [
        ("predicted_outcome", prediction.predicted_outcome),
        ("confidence", prediction.confidence),
        ("status", prediction.get_status_display()),
        ("reasoning", prediction.reasoning or "—"),
        ("created_at", prediction.created_at.isoformat() if prediction.created_at else "—"),
        ("resolved_at", prediction.resolved_at.isoformat() if prediction.resolved_at else "—"),
        ("is_correct", prediction.is_correct),
    ]
    sections = [{
        "title": "Platform prediction",
        "groups": [{
            "title": "Prediction record",
            "fields": [
                {"key": k, "value": _format_value(v)[0], "type": _format_value(v)[1]}
                for k, v in fields
            ],
        }],
    }]
    snapshot = prediction.probability_at_prediction_time or {}
    if snapshot:
        sections[0]["groups"].append({
            "title": "Polymarket odds at prediction time",
            "fields": [
                {"key": label, "value": _format_value(prob)[0], "type": "percent"}
                for label, prob in snapshot.items()
            ],
        })
    return sections
