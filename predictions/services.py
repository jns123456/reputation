"""Prediction business logic."""

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from integrations.attestation_services import (
    record_prediction_claim_attestation_safely,
    record_prediction_resolution_attestation_safely,
)
from markets.models import Market
from predictions.models import Prediction
from predictions.selectors import get_user_active_prediction
from reputation.services import apply_reputation_for_prediction, apply_reputation_for_prediction_exit


def _refresh_market_odds(market):
    """Fetch latest Polymarket odds before recording a forecast snapshot."""
    if market.source == Market.Source.POLYMARKET and market.external_id:
        from integrations.services import refresh_market_from_polymarket

        return refresh_market_from_polymarket(market)
    return market


def build_duplicate_forecast_error(*, user, market):
    """User-facing error when a second open forecast on the same event is blocked."""
    from challenges.selectors import get_active_challenge_contexts_for_market

    challenges = get_active_challenge_contexts_for_market(user=user, market=market)
    if challenges:
        titles = ", ".join(challenge.display_title for challenge in challenges[:2])
        extra = len(challenges) - 2
        if extra > 0:
            titles = f"{titles} (+{extra})"
        return _(
            "You already have an open forecast on this challenge event (%(challenges)s). "
            "Only one open forecast is allowed per event — exit your current position first. "
            "It already counts toward the challenge leaderboard and your global reputation."
        ) % {"challenges": titles}
    return _(
        "You already have an open forecast on this market. "
        "Only one open forecast is allowed per event — exit it before placing another."
    )


def create_prediction(*, user, market, predicted_outcome, predicted_direction=Prediction.Direction.YES, reasoning=""):
    market = _refresh_market_odds(market)
    if not market.is_open:
        raise ValueError(_("Cannot predict on a closed or resolved market."))
    if get_user_active_prediction(user, market):
        raise ValueError(build_duplicate_forecast_error(user=user, market=market))

    probability_snapshot = dict(market.current_probability or {})

    try:
        with transaction.atomic():
            prediction = Prediction.objects.create(
                user=user,
                market=market,
                predicted_outcome=predicted_outcome,
                predicted_direction=predicted_direction,
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

            transaction.on_commit(lambda: record_prediction_claim_attestation_safely(prediction))
    except IntegrityError as exc:
        if "unique_pending_prediction_per_user_market" in str(exc):
            raise ValueError(build_duplicate_forecast_error(user=user, market=market)) from exc
        raise

    from accounts.notification_services import notify_followers_of_prediction
    from accounts.streak_services import record_activity

    notify_followers_of_prediction(prediction=prediction)
    record_activity(user)

    return prediction


def update_prediction(*, prediction, user, predicted_outcome, predicted_direction=Prediction.Direction.YES, reasoning=""):
    """Create a new prediction record superseding the old one for traceability."""
    if prediction.user_id != user.id:
        raise PermissionError(_("Cannot edit another user's prediction."))
    if not prediction.is_editable:
        raise ValueError(_("This prediction cannot be edited."))

    market = _refresh_market_odds(prediction.market)

    with transaction.atomic():
        new_prediction = Prediction.objects.create(
            user=user,
            market=market,
            predicted_outcome=predicted_outcome,
            predicted_direction=predicted_direction,
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


def exit_prediction(*, prediction, user):
    """Close an active forecast and realize reputation based on odds movement."""
    if prediction.user_id != user.id:
        raise PermissionError(_("Cannot exit another user's prediction."))
    if prediction.status != Prediction.Status.PENDING:
        raise ValueError(_("Only active forecasts can be exited."))

    _refresh_market_odds(prediction.market)

    with transaction.atomic():
        prediction = (
            Prediction.objects.select_for_update()
            .select_related("user", "user__profile", "market")
            .get(pk=prediction.pk)
        )
        if prediction.user_id != user.id:
            raise PermissionError(_("Cannot exit another user's prediction."))
        if prediction.status != Prediction.Status.PENDING:
            raise ValueError(_("Only active forecasts can be exited."))
        if not prediction.market.is_open:
            raise ValueError(_("Cannot exit a forecast after the market has closed."))

        prediction.status = Prediction.Status.EXITED
        prediction.probability_at_exit_time = dict(prediction.market.current_probability or {})
        prediction.exited_at = timezone.now()
        prediction.save(
            update_fields=[
                "status",
                "probability_at_exit_time",
                "exited_at",
                "updated_at",
            ]
        )

        profile = prediction.user.profile
        profile.neutral_prediction_count = max(0, profile.neutral_prediction_count - 1)
        profile.save(update_fields=["neutral_prediction_count", "updated_at"])

        apply_reputation_for_prediction_exit(prediction)

    return prediction


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
        outcome_matches = prediction.predicted_outcome.lower() == market.resolved_outcome.lower()
        is_correct = outcome_matches if prediction.predicted_direction == Prediction.Direction.YES else not outcome_matches
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
        transaction.on_commit(lambda p=prediction: record_prediction_resolution_attestation_safely(p))
        resolved.append(prediction)

    from challenges.services import check_challenge_completion

    check_challenge_completion(market=market)

    return resolved
