"""MCP tool handlers (AGENTS.md §17).

Every handler is a thin adapter over existing selectors/services — it must NOT
duplicate business logic, bypass permissions, or skip the scoring/moderation
rules enforced by those services. Write handlers honor ``dry_run``.
"""

from mcp.errors import McpError
from mcp.serializers import serialize_market_card, serialize_market_detail


def _get_user_profile_or_error(*, user_id=None, username=None):
    from accounts.models import UserProfile

    qs = UserProfile.objects.select_related("user")
    if user_id is not None:
        profile = qs.filter(user_id=user_id).first()
    elif username:
        profile = qs.filter(user__username=username).first()
    else:
        raise McpError("invalid_arguments", "Provide user_id or username.")
    if profile is None:
        raise McpError("not_found", "User not found.")
    return profile


def _resolve_market(*, market_id=None, slug=None):
    from markets.models import Market

    qs = Market.objects.all()
    market = None
    if market_id is not None:
        market = qs.filter(pk=market_id).first()
    elif slug:
        market = qs.filter(slug=slug).first()
    if market is None:
        raise McpError("not_found", "Market not found.")
    return market


# --- Read tools --------------------------------------------------------------

def search_markets(*, context, arguments):
    from markets.selectors import get_markets_for_display

    query = (arguments.get("query") or arguments.get("q") or "").strip()
    status = arguments.get("status")
    category = arguments.get("category")
    source = arguments.get("source")
    limit = min(int(arguments.get("limit", 25) or 25), 100)
    markets = get_markets_for_display(
        status=status,
        category=category,
        search=query or None,
        source=source,
        limit=limit,
    )
    return {"count": len(markets), "results": [serialize_market_card(m) for m in markets]}


def get_market(*, context, arguments):
    market = _resolve_market(
        market_id=arguments.get("market_id"),
        slug=arguments.get("slug"),
    )
    return serialize_market_detail(market)


def get_reputation_summary(*, context, arguments):
    profile = _get_user_profile_or_error(
        user_id=arguments.get("user_id"),
        username=arguments.get("username"),
    )
    return {
        "user_id": profile.user_id,
        "username": profile.user.username if profile.user.show_username_publicly else None,
        "reputation_points": profile.reputation_points,
        "reputation_score": profile.reputation_score,
        "prediction_count": profile.prediction_count,
        "correct_prediction_count": profile.correct_prediction_count,
        "incorrect_prediction_count": profile.incorrect_prediction_count,
    }


def get_popularity_summary(*, context, arguments):
    profile = _get_user_profile_or_error(
        user_id=arguments.get("user_id"),
        username=arguments.get("username"),
    )
    return {
        "user_id": profile.user_id,
        "username": profile.user.username if profile.user.show_username_publicly else None,
        "popularity_points": profile.popularity_points,
        "popularity_score": profile.popularity_score,
    }


# --- Write tools (feature-flagged, dry-run capable) --------------------------

def submit_prediction(*, context, arguments):
    """Submit a formal prediction. The agent picks an outcome + optional reasoning;
    the system snapshots the market-implied probability (no confidence %)."""
    from predictions.models import Prediction
    from predictions.services import create_prediction

    user = context.user
    market = _resolve_market(
        market_id=arguments.get("market_id"),
        slug=arguments.get("slug"),
    )
    outcome = (arguments.get("predicted_outcome") or arguments.get("outcome") or "").strip()
    if not outcome:
        raise McpError("invalid_arguments", "predicted_outcome is required.")
    direction = (arguments.get("predicted_direction") or "yes").lower()
    if direction not in Prediction.Direction.values:
        raise McpError("invalid_arguments", "predicted_direction must be 'yes' or 'no'.")
    reasoning = (arguments.get("reasoning") or "")[:2000]

    valid_outcomes = [label.lower() for label in market.outcome_labels]
    if valid_outcomes and outcome.lower() not in valid_outcomes:
        raise McpError("invalid_arguments", "predicted_outcome is not valid for this market.")
    if not market.is_forecastable:
        raise McpError("market_not_forecastable", "This market is not open for forecasts.")

    if context.dry_run:
        return {
            "dry_run": True,
            "would_create": {
                "market_id": market.id,
                "predicted_outcome": outcome,
                "predicted_direction": direction,
            },
        }

    try:
        prediction = create_prediction(
            user=user,
            market=market,
            predicted_outcome=outcome,
            predicted_direction=direction,
            reasoning=reasoning,
        )
    except ValueError as exc:
        raise McpError("rejected", str(exc)) from exc
    return {
        "prediction_id": prediction.id,
        "market_id": market.id,
        "predicted_outcome": prediction.predicted_outcome,
        "predicted_direction": prediction.predicted_direction,
        "probability_at_prediction_time": prediction.probability_at_prediction_time,
        "status": prediction.status,
    }


def submit_comment(*, context, arguments):
    from comments.services import create_comment

    user = context.user
    market = _resolve_market(
        market_id=arguments.get("market_id"),
        slug=arguments.get("slug"),
    )
    body = (arguments.get("body") or "").strip()
    if not body:
        raise McpError("invalid_arguments", "body is required.")
    body = body[:5000]

    # Anti-spam / quality gate shared with the human path (§16).
    from accounts.abuse_services import assess_content

    assessment = assess_content(user=user, text=body, scope="mcp:submit_comment")
    if assessment["is_spam"]:
        raise McpError("spam_rejected", "Comment rejected by anti-spam checks.")

    parent_comment = None
    parent_id = arguments.get("parent_comment_id")
    if parent_id:
        from comments.models import Comment

        parent_comment = Comment.objects.filter(pk=parent_id).first()
        if parent_comment is None:
            raise McpError("not_found", "parent_comment_id not found.")

    if context.dry_run:
        return {
            "dry_run": True,
            "would_create": {"market_id": market.id, "body_length": len(body)},
        }

    try:
        comment = create_comment(
            user=user,
            market=market,
            body=body,
            parent_comment=parent_comment,
        )
    except ValueError as exc:
        raise McpError("rejected", str(exc)) from exc
    return {"comment_id": comment.id, "market_id": market.id}
