"""Prediction business logic."""

from django.db import transaction
from django.utils import timezone

from markets.models import Market
from predictions.models import Prediction
from reputation.services import apply_reputation_for_prediction


def _refresh_market_odds(market):
    """Fetch latest Polymarket odds before recording a forecast snapshot."""
    if market.source == Market.Source.POLYMARKET and market.external_id:
        from integrations.services import refresh_market_from_polymarket

        return refresh_market_from_polymarket(market)
    return market


def create_prediction(*, user, market, predicted_outcome, reasoning=""):
    market = _refresh_market_odds(market)
    if not market.is_open:
        raise ValueError("Cannot predict on a closed or resolved market.")

    probability_snapshot = dict(market.current_probability or {})

    with transaction.atomic():
        prediction = Prediction.objects.create(
            user=user,
            market=market,
            predicted_outcome=predicted_outcome,
            probability_at_prediction_time=probability_snapshot,
            reasoning=reasoning,
        )
        profile = user.profile
        profile.prediction_count += 1
        profile.neutral_prediction_count += 1
        profile.save(update_fields=["prediction_count", "neutral_prediction_count", "updated_at"])

        from accounts.category_stats_services import (
            apply_category_prediction_created,
            resolve_category_from_market,
        )

        apply_category_prediction_created(user, resolve_category_from_market(market))

    return prediction


def update_prediction(*, prediction, user, predicted_outcome, reasoning=""):
    """Create a new prediction record superseding the old one for traceability."""
    if prediction.user_id != user.id:
        raise PermissionError("Cannot edit another user's prediction.")
    if not prediction.is_editable:
        raise ValueError("This prediction cannot be edited.")

    market = _refresh_market_odds(prediction.market)

    with transaction.atomic():
        new_prediction = Prediction.objects.create(
            user=user,
            market=market,
            predicted_outcome=predicted_outcome,
            probability_at_prediction_time=dict(market.current_probability or {}),
            reasoning=reasoning,
        )
        prediction.superseded_by = new_prediction
        prediction.status = Prediction.Status.VOID
        prediction.save(update_fields=["superseded_by", "status", "updated_at"])

        profile = user.profile
        profile.neutral_prediction_count = max(0, profile.neutral_prediction_count - 1)
        profile.prediction_count += 1
        profile.neutral_prediction_count += 1
        profile.save(
            update_fields=["prediction_count", "neutral_prediction_count", "updated_at"]
        )

        from accounts.category_stats_services import (
            apply_category_prediction_created,
            resolve_category_from_market,
        )

        apply_category_prediction_created(user, resolve_category_from_market(market))

    return new_prediction


def resolve_market_predictions(market):
    """Resolve all pending predictions when a market is resolved."""
    if market.status != market.Status.RESOLVED or not market.resolved_outcome:
        return []

    resolved = []
    predictions = Prediction.objects.filter(
        market=market,
        status=Prediction.Status.PENDING,
    ).select_related("user", "user__profile")

    for prediction in predictions:
        is_correct = prediction.predicted_outcome.lower() == market.resolved_outcome.lower()
        prediction.status = Prediction.Status.RESOLVED
        prediction.is_correct = is_correct
        prediction.resolved_at = timezone.now()
        prediction.save(
            update_fields=["status", "is_correct", "resolved_at", "updated_at"]
        )

        profile = prediction.user.profile
        profile.neutral_prediction_count = max(0, profile.neutral_prediction_count - 1)
        profile.save(update_fields=["neutral_prediction_count", "updated_at"])

        apply_reputation_for_prediction(prediction)
        resolved.append(prediction)

    return resolved
