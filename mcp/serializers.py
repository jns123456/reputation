"""Plain-dict serializers for MCP payloads (no request context needed).

Kept separate from DRF serializers so MCP handlers stay request-agnostic and
only expose public, non-sensitive fields.
"""


def serialize_market_card(market):
    return {
        "id": market.id,
        "slug": market.slug,
        "title": getattr(market, "display_title", None) or market.title,
        "category": market.category,
        "status": market.status,
        "source": market.source,
        "close_date": market.close_date.isoformat() if market.close_date else None,
        "is_forecastable": market.is_forecastable,
    }


def serialize_market_detail(market):
    data = serialize_market_card(market)
    data.update(
        {
            "external_id": market.external_id,
            "description": market.description,
            "outcomes": market.outcome_labels,
            "current_probability": market.current_probability,
            "resolution_date": (
                market.resolution_date.isoformat() if market.resolution_date else None
            ),
            "resolved_outcome": market.resolved_outcome,
        }
    )
    return data


def serialize_public_profile(profile):
    user = profile.user
    return {
        "user_id": user.id,
        "username": user.username if user.show_username_publicly else None,
        "display_name": user.public_name,
        "account_type": user.account_type,
        "is_ai_agent": user.is_ai_agent,
        "is_verified": user.is_verified,
        "reputation": {
            "reputation_points": profile.reputation_points,
            "reputation_score": profile.reputation_score,
            "scored_forecast_count": profile.scored_forecast_count,
            "prediction_count": profile.prediction_count,
            "correct_prediction_count": profile.correct_prediction_count,
            "incorrect_prediction_count": profile.incorrect_prediction_count,
        },
        "popularity": {
            "popularity_points": profile.popularity_points,
            "popularity_score": profile.popularity_score,
        },
    }
