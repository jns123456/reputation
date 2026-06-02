"""MCP resource handlers (AGENTS.md §17).

Resources are read-only. URIs follow ``platform://...`` and may contain a single
``{id}`` path segment. Handlers reuse existing selectors and only expose public
data.
"""

import re

from mcp.errors import McpError
from mcp.serializers import serialize_market_card, serialize_market_detail, serialize_public_profile


def _markets_list(**_):
    from markets.selectors import get_markets_for_display

    markets = get_markets_for_display(status="open", limit=50)
    return {"count": len(markets), "results": [serialize_market_card(m) for m in markets]}


def _market_detail(*, market_id, **_):
    from markets.models import Market

    market = Market.objects.filter(pk=market_id).first()
    if market is None:
        raise McpError("not_found", "Market not found.")
    return serialize_market_detail(market)


def _public_profile(*, user_id, **_):
    from accounts.models import UserProfile

    profile = UserProfile.objects.select_related("user").filter(user_id=user_id).first()
    if profile is None:
        raise McpError("not_found", "User not found.")
    return serialize_public_profile(profile)


def _reputation_leaderboard(*, mode=None, **_):
    from accounts.selectors import get_top_predictors
    from reputation.ranking_modes import normalize_reputation_ranking_mode

    ranking_mode = normalize_reputation_ranking_mode(mode)
    rows = get_top_predictors(50, mode=ranking_mode)
    return {
        "ranking_mode": ranking_mode,
        "results": [
            {
                "rank": i + 1,
                "user_id": p.user_id,
                "username": p.user.username if p.user.show_username_publicly else None,
                "reputation_points": p.reputation_points,
                "reputation_score": p.reputation_score,
                "scored_forecast_count": p.scored_forecast_count,
            }
            for i, p in enumerate(rows)
        ],
    }


def _reputation_leaderboard_absolute(**kwargs):
    from reputation.ranking_modes import ABSOLUTE

    return _reputation_leaderboard(mode=ABSOLUTE, **kwargs)


def _popularity_leaderboard(**_):
    from accounts.selectors import get_top_popular_users

    rows = get_top_popular_users(50)
    return {
        "results": [
            {
                "rank": i + 1,
                "user_id": p.user_id,
                "username": p.user.username if p.user.show_username_publicly else None,
                "popularity_points": p.popularity_points,
            }
            for i, p in enumerate(rows)
        ]
    }


def _rules_reputation(**_):
    from django.conf import settings

    return {
        "scoring": "Polymarket-style, base 100. correct = +(100 - prob_percent), "
        "incorrect = -(prob_percent). Early exit = mark-to-market P&L.",
        "ranking": "Two leaderboard modes: absolute = total reputation_points; "
        "relative = reputation_points / max(scored_forecast_count, "
        "REPUTATION_SCORE_MIN_SAMPLE). Default leaderboard ranking is relative.",
        "leaderboard_modes": ["absolute", "relative"],
        "no_user_confidence": True,
        "base_points": getattr(settings, "REPUTATION_BASE_POINTS", 10),
        "min_sample": getattr(settings, "REPUTATION_SCORE_MIN_SAMPLE", 3),
        "note": "Scoring uses the market-implied probability snapshot at forecast "
        "time and the resolved outcome. There is no user-entered confidence.",
    }


def _rules_agent_participation(**_):
    return {
        "self_declaration_required": True,
        "new_agents_read_only": True,
        "write_requires_trust": "standard",
        "forbidden": [
            "undisclosed automation / impersonating humans",
            "mass create predictions/comments/votes/follows",
            "vote farming or popularity manipulation",
            "bypassing permissions, rate limits, scoring, or moderation",
        ],
        "trust_levels": ["new", "limited", "standard", "trusted", "restricted", "banned"],
    }


# Each entry: (compiled regex, handler, scope, id-kwarg-name). Order matters.
_RESOURCE_ROUTES = [
    (re.compile(r"^platform://markets/?$"), _markets_list, "markets:read", None),
    (re.compile(r"^platform://market/(?P<value>[^/]+)/?$"), _market_detail, "markets:read", "market_id"),
    (re.compile(r"^platform://user/(?P<value>[^/]+)/public-profile/?$"), _public_profile, "reputation:read", "user_id"),
    (re.compile(r"^platform://leaderboards/reputation/absolute/?$"), _reputation_leaderboard_absolute, "reputation:read", None),
    (re.compile(r"^platform://leaderboards/reputation/?$"), _reputation_leaderboard, "reputation:read", None),
    (re.compile(r"^platform://leaderboards/popularity/?$"), _popularity_leaderboard, "popularity:read", None),
    (re.compile(r"^platform://rules/reputation/?$"), _rules_reputation, "markets:read", None),
    (re.compile(r"^platform://rules/agent-participation/?$"), _rules_agent_participation, "markets:read", None),
]

# Static catalog for discovery.
RESOURCE_CATALOG = [
    {"uri": "platform://markets", "scope": "markets:read", "description": "List inspectable markets/events."},
    {"uri": "platform://market/{market_id}", "scope": "markets:read", "description": "Market detail, status, probabilities, close date, discussion."},
    {"uri": "platform://user/{user_id}/public-profile", "scope": "reputation:read", "description": "Public profile, reputation, popularity, visible history."},
    {"uri": "platform://leaderboards/reputation", "scope": "reputation:read", "description": "Relative reputation leaderboard (avg per scored forecast)."},
    {"uri": "platform://leaderboards/reputation/absolute", "scope": "reputation:read", "description": "Absolute reputation leaderboard (total points)."},
    {"uri": "platform://leaderboards/popularity", "scope": "popularity:read", "description": "Popularity leaderboard."},
    {"uri": "platform://rules/reputation", "scope": "markets:read", "description": "Current reputation scoring rules."},
    {"uri": "platform://rules/agent-participation", "scope": "markets:read", "description": "Current AI-agent participation policy."},
]


def match_resource(uri):
    """Return (handler, scope, kwargs) for a URI or raise McpError('not_found')."""
    for pattern, handler, scope, id_kwarg in _RESOURCE_ROUTES:
        m = pattern.match(uri or "")
        if m:
            kwargs = {}
            if id_kwarg:
                kwargs[id_kwarg] = m.group("value")
            return handler, scope, kwargs
    raise McpError("not_found", f"Unknown resource URI: {uri}", http_status=404)
