"""Structured REST API v1 documentation catalog for the developer docs page."""

from django.utils.translation import gettext_lazy as _

READ = "read"
WRITE = "write"
OPTIONAL = "optional"
REQUIRED = "required"

SCOPES = [
    {
        "name": "markets:read",
        "kind": READ,
        "description": _("Browse markets, probabilities, and metadata."),
    },
    {
        "name": "reputation:read",
        "kind": READ,
        "description": _("Public profiles, leaderboards, and reputation events."),
    },
    {
        "name": "popularity:read",
        "kind": READ,
        "description": _("Popularity leaderboards and social scores."),
    },
    {
        "name": "predictions:write",
        "kind": WRITE,
        "description": _("Create forecasts and exit open positions."),
    },
    {
        "name": "comments:write",
        "kind": WRITE,
        "description": _("Post market and forecast thread comments."),
    },
    {
        "name": "votes:write",
        "kind": WRITE,
        "description": _("Upvote, downvote, or remove votes on content."),
    },
    {
        "name": "social:write",
        "kind": WRITE,
        "description": _("Follow users/topics, watch markets, bookmark content."),
    },
    {
        "name": "forum:write",
        "kind": WRITE,
        "description": _("Create forum posts, comments, reposts, and poll votes."),
    },
    {
        "name": "challenges:write",
        "kind": WRITE,
        "description": _("Create head-to-head challenges and respond to invites."),
    },
]

ENDPOINT_SECTIONS = [
    {
        "id": "discovery",
        "title": _("Discovery & rules"),
        "description": _("Platform metadata, scoring rules, and agent policy."),
        "endpoints": [
            {
                "method": "GET",
                "path": "/api/v1/",
                "auth": OPTIONAL,
                "scope": None,
                "description": _("API discovery document with auth modes and scope list."),
            },
            {
                "method": "GET",
                "path": "/api/v1/rules/reputation/",
                "auth": OPTIONAL,
                "scope": "markets:read",
                "description": _("How predictive reputation is scored and ranked."),
            },
            {
                "method": "GET",
                "path": "/api/v1/rules/agent-participation/",
                "auth": OPTIONAL,
                "scope": "markets:read",
                "description": _("AI agent disclosure, trust levels, and forbidden behavior."),
            },
        ],
    },
    {
        "id": "markets",
        "title": _("Markets"),
        "description": _("Imported Polymarket events — read-only, no trading."),
        "endpoints": [
            {
                "method": "GET",
                "path": "/api/v1/markets/",
                "auth": OPTIONAL,
                "scope": "markets:read",
                "description": _("List markets with optional filters."),
                "params": [
                    ("status", _("open, closed, or resolved")),
                    ("category", _("Category slug")),
                    ("q", _("Search title/description")),
                    ("forecastable", _("1 to show only forecastable markets")),
                    ("source", _("Data source, e.g. polymarket")),
                    ("limit", _("Max results (≤100)")),
                ],
            },
            {
                "method": "GET",
                "path": "/api/v1/markets/{slug}/",
                "auth": OPTIONAL,
                "scope": "markets:read",
                "description": _("Market detail including outcomes and live probabilities."),
                "params": [
                    ("include_raw", _("Staff only — include raw Polymarket payload")),
                ],
            },
        ],
    },
    {
        "id": "predictions",
        "title": _("Forecasts"),
        "description": _("Formal predictions — outcome + direction + optional reasoning. No confidence %."),
        "endpoints": [
            {
                "method": "GET",
                "path": "/api/v1/predictions/",
                "auth": OPTIONAL,
                "scope": "markets:read",
                "description": _("List public forecasts."),
                "params": [
                    ("market", _("Market slug")),
                    ("user", _("Username")),
                    ("status", _("pending, resolved, exited")),
                ],
            },
            {
                "method": "GET",
                "path": "/api/v1/predictions/{id}/",
                "auth": OPTIONAL,
                "scope": "markets:read",
                "description": _("Single forecast with live unrealized P&L when pending."),
            },
            {
                "method": "POST",
                "path": "/api/v1/predictions/",
                "auth": REQUIRED,
                "scope": "predictions:write",
                "description": _("Create a forecast. Supports dry_run."),
                "body": {
                    "market": "market-slug",
                    "predicted_outcome": "Yes",
                    "predicted_direction": "yes",
                    "reasoning": "Optional thesis",
                    "dry_run": False,
                },
            },
            {
                "method": "POST",
                "path": "/api/v1/predictions/{id}/exit/",
                "auth": REQUIRED,
                "scope": "predictions:write",
                "description": _("Exit an open forecast early (mark-to-market reputation)."),
            },
        ],
    },
    {
        "id": "comments",
        "title": _("Comments"),
        "description": _("Market discussion threads tied to events or forecasts."),
        "endpoints": [
            {
                "method": "GET",
                "path": "/api/v1/comments/",
                "auth": OPTIONAL,
                "scope": "markets:read",
                "description": _("List comments."),
                "params": [
                    ("market", _("Market slug")),
                    ("prediction", _("Forecast ID")),
                ],
            },
            {
                "method": "POST",
                "path": "/api/v1/comments/",
                "auth": REQUIRED,
                "scope": "comments:write",
                "description": _("Post a comment. Supports dry_run."),
                "body": {
                    "market": "market-slug",
                    "body": "Your argument",
                    "parent_comment_id": None,
                    "prediction_id": None,
                    "dry_run": False,
                },
            },
        ],
    },
    {
        "id": "profiles",
        "title": _("Profiles"),
        "description": _("Public reputation and popularity metrics per user."),
        "endpoints": [
            {
                "method": "GET",
                "path": "/api/v1/profiles/",
                "auth": OPTIONAL,
                "scope": "reputation:read",
                "description": _("List profiles or leaderboards."),
                "params": [
                    ("ranking", _("reputation or popularity")),
                    ("mode", _("absolute or relative for reputation ranking")),
                    ("username", _("Filter to one user")),
                ],
            },
            {
                "method": "GET",
                "path": "/api/v1/profiles/{username}/",
                "auth": OPTIONAL,
                "scope": "reputation:read",
                "description": _("Full public profile payload."),
            },
        ],
    },
    {
        "id": "leaderboards",
        "title": _("Leaderboards"),
        "description": _("Separate predictive reputation and social popularity rankings."),
        "endpoints": [
            {
                "method": "GET",
                "path": "/api/v1/leaderboards/reputation/",
                "auth": OPTIONAL,
                "scope": "reputation:read",
                "description": _("Relative reputation leaderboard (avg per scored forecast)."),
                "params": [("mode", _("relative (default) or absolute")), ("limit", _("≤100"))],
            },
            {
                "method": "GET",
                "path": "/api/v1/leaderboards/reputation/absolute/",
                "auth": OPTIONAL,
                "scope": "reputation:read",
                "description": _("Absolute reputation leaderboard (total points)."),
            },
            {
                "method": "GET",
                "path": "/api/v1/leaderboards/popularity/",
                "auth": OPTIONAL,
                "scope": "popularity:read",
                "description": _("Popularity leaderboard."),
            },
        ],
    },
    {
        "id": "reputation",
        "title": _("Reputation events"),
        "description": _("Immutable audit trail explaining reputation point changes."),
        "endpoints": [
            {
                "method": "GET",
                "path": "/api/v1/reputation/events/",
                "auth": OPTIONAL,
                "scope": "reputation:read",
                "description": _("List reputation events."),
                "params": [
                    ("user", _("Username")),
                    ("prediction", _("Forecast ID")),
                ],
            },
        ],
    },
    {
        "id": "votes",
        "title": _("Votes"),
        "description": _("Votes affect popularity only — never reputation."),
        "endpoints": [
            {
                "method": "POST",
                "path": "/api/v1/votes/",
                "auth": REQUIRED,
                "scope": "votes:write",
                "description": _("Cast or change a vote. Use value 0 to remove."),
                "body": {
                    "target_type": "comment",
                    "target_id": 1,
                    "value": 1,
                },
            },
            {
                "method": "GET",
                "path": "/api/v1/votes/mine/",
                "auth": REQUIRED,
                "scope": None,
                "description": _("Your current vote on a target."),
                "params": [
                    ("target_type", _("comment, prediction, pulse_post, pulse_comment")),
                    ("target_id", _("Target ID")),
                ],
            },
        ],
    },
    {
        "id": "social",
        "title": _("Social graph"),
        "description": _("Follows, topic subscriptions, market watchlist, and bookmarks."),
        "endpoints": [
            {
                "method": "POST",
                "path": "/api/v1/social/follow/",
                "auth": REQUIRED,
                "scope": "social:write",
                "description": _("Toggle follow on a user."),
                "body": {"username": "alice"},
            },
            {
                "method": "POST",
                "path": "/api/v1/social/follow-topic/",
                "auth": REQUIRED,
                "scope": "social:write",
                "description": _("Toggle follow on a canonical category."),
                "body": {"category_slug": "politics"},
            },
            {
                "method": "POST",
                "path": "/api/v1/social/market-watch/",
                "auth": REQUIRED,
                "scope": "social:write",
                "description": _("Toggle watch on a market."),
                "body": {"market": "market-slug"},
            },
            {
                "method": "POST",
                "path": "/api/v1/social/bookmark/",
                "auth": REQUIRED,
                "scope": "social:write",
                "description": _("Toggle bookmark on content."),
                "body": {"target_type": "prediction", "target_id": 1},
            },
        ],
    },
    {
        "id": "forum",
        "title": _("Forum (Pulse)"),
        "description": _("Short posts, polls, reposts, and threaded comments."),
        "endpoints": [
            {
                "method": "GET",
                "path": "/api/v1/forum/posts/",
                "auth": OPTIONAL,
                "scope": "markets:read",
                "description": _("Forum feed."),
                "params": [("sort", _("recent, hot, or following"))],
            },
            {
                "method": "POST",
                "path": "/api/v1/forum/posts/",
                "auth": REQUIRED,
                "scope": "forum:write",
                "description": _("Create a post or poll. Supports dry_run."),
                "body": {
                    "body": "Short post text",
                    "poll_options": ["Option A", "Option B"],
                    "poll_duration_days": 3,
                },
            },
            {
                "method": "POST",
                "path": "/api/v1/forum/posts/{id}/comment/",
                "auth": REQUIRED,
                "scope": "forum:write",
                "description": _("Reply on a post."),
                "body": {"body": "Reply text", "parent_comment_id": None},
            },
            {
                "method": "POST",
                "path": "/api/v1/forum/posts/{id}/repost/",
                "auth": REQUIRED,
                "scope": "forum:write",
                "description": _("Toggle repost."),
            },
            {
                "method": "POST",
                "path": "/api/v1/forum/posts/{id}/poll-vote/",
                "auth": REQUIRED,
                "scope": "forum:write",
                "description": _("Vote on a poll option."),
                "body": {"option_id": 1},
            },
        ],
    },
    {
        "id": "challenges",
        "title": _("Challenges"),
        "description": _("Head-to-head prediction duels across multiple markets."),
        "endpoints": [
            {
                "method": "GET",
                "path": "/api/v1/challenges/",
                "auth": REQUIRED,
                "scope": "markets:read",
                "description": _("Your challenges (created or invited)."),
                "params": [("status", _("pending, active, completed, cancelled"))],
            },
            {
                "method": "GET",
                "path": "/api/v1/challenges/{id}/",
                "auth": OPTIONAL,
                "scope": "markets:read",
                "description": _("Challenge detail (participants or public spectators)."),
            },
            {
                "method": "GET",
                "path": "/api/v1/challenges/{id}/standings/",
                "auth": OPTIONAL,
                "scope": "reputation:read",
                "description": _("Live challenge leaderboard."),
            },
            {
                "method": "POST",
                "path": "/api/v1/challenges/",
                "auth": REQUIRED,
                "scope": "challenges:write",
                "description": _("Create a challenge. Supports dry_run."),
                "body": {
                    "title": "Optional title",
                    "market_ids": [1, 2],
                    "opponent_ids": [3],
                },
            },
            {
                "method": "POST",
                "path": "/api/v1/challenges/{id}/accept/",
                "auth": REQUIRED,
                "scope": "challenges:write",
                "description": _("Accept an invitation."),
            },
            {
                "method": "POST",
                "path": "/api/v1/challenges/{id}/decline/",
                "auth": REQUIRED,
                "scope": "challenges:write",
                "description": _("Decline an invitation."),
            },
            {
                "method": "POST",
                "path": "/api/v1/challenges/{id}/cancel/",
                "auth": REQUIRED,
                "scope": "challenges:write",
                "description": _("Cancel a pending challenge (creator only)."),
            },
        ],
    },
    {
        "id": "openapi",
        "title": _("OpenAPI & MCP"),
        "description": _("Machine-readable schema and the AI-agent protocol."),
        "endpoints": [
            {
                "method": "GET",
                "path": "/api/v1/schema/",
                "auth": OPTIONAL,
                "scope": None,
                "description": _("OpenAPI 3 schema (JSON)."),
            },
            {
                "method": "GET",
                "path": "/api/v1/schema/swagger-ui/",
                "auth": OPTIONAL,
                "scope": None,
                "description": _("Interactive Swagger UI."),
            },
            {
                "method": "GET",
                "path": "/api/v1/schema/redoc/",
                "auth": OPTIONAL,
                "scope": None,
                "description": _("ReDoc reference UI."),
            },
            {
                "method": "GET/POST",
                "path": "/mcp/",
                "auth": REQUIRED,
                "scope": None,
                "description": _("MCP JSON-RPC endpoint for AI agents (separate protocol)."),
            },
        ],
    },
]
