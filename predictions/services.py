"""Prediction business logic."""

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from integrations.attestation_services import (
    record_prediction_claim_attestation_safely,
    record_prediction_resolution_attestation_safely,
)
from accounts.models import SubscriberAudience
from accounts.monetization_services import validate_creator_audience
from predictions.models import Prediction
from predictions.selectors import clear_forecasts_market_options_cache, get_user_active_prediction
from reputation.services import (
    apply_reputation_for_prediction,
    apply_reputation_for_prediction_exit,
    calculate_exit_reputation_delta,
    calculate_reputation_delta,
    calculate_reputation_stakes,
    calculate_unrealized_reputation,
    get_predicted_outcome_probability,
)


def _refresh_market_odds(market):
    """Queue a non-blocking odds refresh; never call Polymarket inside the request.

    The forecast snapshot uses the latest odds already persisted in the DB. A
    background task keeps those odds fresh (see ``integrations.celery_utils``),
    so we avoid blocking the HTTP worker on Polymarket latency — and the platform
    stays usable when Polymarket is slow or unavailable.
    """
    from integrations.celery_utils import enqueue_market_refresh_if_stale

    enqueue_market_refresh_if_stale(market)
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


def create_prediction(
    *,
    user,
    market,
    predicted_outcome,
    predicted_direction=Prediction.Direction.YES,
    reasoning="",
    audience=None,
):
    from accounts.write_guard import guard_write_action

    guard_write_action(
        action="prediction",
        user=user,
        text=reasoning,
        content_scope="write:prediction",
    )

    market = _refresh_market_odds(market)
    if not market.is_open:
        raise ValueError(_("Cannot predict on a closed or resolved market."))
    if market.is_in_play:
        raise ValueError(_("This event has already started and is no longer accepting forecasts."))
    if market.is_expired or not market.accepting_orders:
        raise ValueError(_("This market has already closed and is no longer accepting forecasts."))
    if get_user_active_prediction(user, market):
        raise ValueError(build_duplicate_forecast_error(user=user, market=market))

    resolved_audience = audience or SubscriberAudience.PUBLIC
    validate_creator_audience(user=user, audience=resolved_audience)

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
                audience=resolved_audience,
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
            transaction.on_commit(clear_forecasts_market_options_cache)
    except IntegrityError as exc:
        if "unique_pending_prediction_per_user_market" in str(exc):
            raise ValueError(build_duplicate_forecast_error(user=user, market=market)) from exc
        raise

    from accounts.mission_services import (
        ACTION_PREDICTION,
        ACTION_REASONED_PREDICTION,
        REASONED_PREDICTION_MIN_CHARS,
        record_mission_action,
    )
    from accounts.notification_services import notify_followers_of_prediction
    from accounts.streak_services import record_activity

    notify_followers_of_prediction(prediction=prediction)
    record_activity(user)
    record_mission_action(user, ACTION_PREDICTION)
    if len((reasoning or "").strip()) >= REASONED_PREDICTION_MIN_CHARS:
        record_mission_action(user, ACTION_REASONED_PREDICTION)

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

        # Replacing a pending forecast does not change aggregate profile counters.

    return new_prediction


def exit_prediction(*, prediction, user):
    """Close an active forecast and realize reputation based on odds movement."""
    if prediction.user_id != user.id:
        raise PermissionError(_("Cannot exit another user's prediction."))
    if prediction.status != Prediction.Status.PENDING:
        raise ValueError(_("Only active forecasts can be exited."))

    _refresh_market_odds(prediction.market)

    with transaction.atomic():
        from accounts.models import UserProfile

        prediction = (
            Prediction.objects.select_for_update(of=("self",))
            .select_related("user", "market")
            .get(pk=prediction.pk)
        )
        if prediction.user_id != user.id:
            raise PermissionError(_("Cannot exit another user's prediction."))
        if prediction.status != Prediction.Status.PENDING:
            raise ValueError(_("Only active forecasts can be exited."))
        market = prediction.market
        if not market.is_open:
            raise ValueError(_("Cannot exit a forecast after the market has closed."))
        if market.is_in_play:
            raise ValueError(_("Cannot exit a forecast after the event has started."))

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

        profile = UserProfile.objects.select_for_update().get(user=prediction.user)
        profile.neutral_prediction_count = max(0, profile.neutral_prediction_count - 1)
        profile.save(update_fields=["neutral_prediction_count", "updated_at"])

        apply_reputation_for_prediction_exit(prediction)

    return prediction


def resolve_eliminated_outcome_predictions(market, *, raw_event=None):
    """Resolve pending forecasts whose outcome bucket has definitively lost.

    Tournament-style grouped events (e.g. French Open winner) often stay ``open``
    until the champion is known, but eliminated players' sub-markets close at 0.
    """
    from markets.models import Market

    if market.status == Market.Status.RESOLVED:
        return []

    from integrations.polymarket.client import (
        _grouped_outcome_markets,
        grouped_outcome_bucket_lost,
    )
    event = raw_event or market.polymarket_event_raw or {}
    if not event.get("markets"):
        return []

    eliminated_labels = []
    for raw_market in _grouped_outcome_markets(event, open_only=False):
        label = str(raw_market.get("groupItemTitle") or "").strip()
        if label and grouped_outcome_bucket_lost(raw_market):
            eliminated_labels.append(label)

    if not eliminated_labels:
        return []

    resolved = []
    predictions = Prediction.objects.filter(
        market=market,
        status=Prediction.Status.PENDING,
    ).select_related("user", "user__profile")

    eliminated_lower = {label.lower(): label for label in eliminated_labels}
    for prediction in predictions:
        pick = (prediction.predicted_outcome or "").strip()
        if pick.lower() not in eliminated_lower:
            continue
        if prediction.predicted_direction != Prediction.Direction.YES:
            continue

        prediction.status = Prediction.Status.RESOLVED
        prediction.is_correct = False
        prediction.resolved_at = timezone.now()
        prediction.save(
            update_fields=["status", "is_correct", "resolved_at", "updated_at"]
        )

        profile = prediction.user.profile
        profile.neutral_prediction_count = max(0, profile.neutral_prediction_count - 1)
        profile.save(update_fields=["neutral_prediction_count", "updated_at"])

        apply_reputation_for_prediction(prediction)
        transaction.on_commit(
            lambda p=prediction: record_prediction_resolution_attestation_safely(p)
        )
        resolved.append(prediction)

    if resolved:
        from challenges.services import check_challenge_completion

        check_challenge_completion(market=market)

    return resolved


def _side_probability_percent(*, prediction, probability_snapshot):
    if not probability_snapshot:
        return None
    return int(
        round(
            get_predicted_outcome_probability(
                prediction.predicted_outcome,
                probability_snapshot,
                predicted_direction=prediction.predicted_direction,
            )
            * 100
        )
    )


def _forecast_realized_reputation_delta(prediction):
    if prediction.status == Prediction.Status.EXITED:
        event = prediction.reputation_events.filter(
            event_type="exited_prediction"
        ).first()
        if event:
            return event.points_delta
        if prediction.probability_at_exit_time:
            return calculate_exit_reputation_delta(
                predicted_outcome=prediction.predicted_outcome,
                entry_probability_snapshot=prediction.probability_at_prediction_time,
                exit_probability_snapshot=prediction.probability_at_exit_time,
                predicted_direction=prediction.predicted_direction,
            )
        return None

    if prediction.status != Prediction.Status.RESOLVED or prediction.is_correct is None:
        return None
    return calculate_reputation_delta(
        is_correct=prediction.is_correct,
        predicted_outcome=prediction.predicted_outcome,
        probability_snapshot=prediction.probability_at_prediction_time,
        predicted_direction=prediction.predicted_direction,
    )


def build_forecast_card_metrics(prediction):
    """Entry/now/P&L display metrics for forecast cards (open book, community feed)."""
    market = prediction.market
    entry_percent = _side_probability_percent(
        prediction=prediction,
        probability_snapshot=prediction.probability_at_prediction_time,
    )
    stakes = calculate_reputation_stakes(
        predicted_outcome=prediction.predicted_outcome,
        probability_snapshot=prediction.probability_at_prediction_time,
        predicted_direction=prediction.predicted_direction,
    )
    metrics = {
        "entry_percent": entry_percent,
        "now_percent": None,
        "pnl_delta": None,
        "middle_label": "now",
        "resolution_if_correct": stakes["win_points"],
        "resolution_if_wrong": -stakes["loss_points"],
        "countdown": None,
        "show_resolution_note": False,
    }

    if prediction.status == Prediction.Status.PENDING:
        metrics["now_percent"] = _side_probability_percent(
            prediction=prediction,
            probability_snapshot=market.current_probability or {},
        )
        metrics["pnl_delta"] = calculate_unrealized_reputation(prediction)
        metrics["middle_label"] = "now"
        metrics["countdown"] = market.expiration_countdown
        metrics["show_resolution_note"] = True
        return metrics

    if prediction.status == Prediction.Status.EXITED:
        metrics["now_percent"] = _side_probability_percent(
            prediction=prediction,
            probability_snapshot=prediction.probability_at_exit_time,
        )
        metrics["pnl_delta"] = _forecast_realized_reputation_delta(prediction)
        metrics["middle_label"] = "exit"
        return metrics

    if prediction.status == Prediction.Status.RESOLVED:
        metrics["now_percent"] = 100 if prediction.is_correct else 0
        metrics["pnl_delta"] = _forecast_realized_reputation_delta(prediction)
        metrics["middle_label"] = "resolution"
        return metrics

    return metrics


def prediction_is_correct_for_resolved_market(market, prediction):
    """Return whether a forecast should score as correct for a resolved market."""
    from markets.forecast_modes import ForecastMode, get_forecast_mode

    if get_forecast_mode(market) == ForecastMode.MULTI_BINARY:
        from integrations.polymarket.client import grouped_submarket_resolved_yes

        event = market.polymarket_event_raw or {}
        sub_resolved_yes = grouped_submarket_resolved_yes(event, prediction.predicted_outcome)
        if sub_resolved_yes is None:
            # Multi-binary events may resolve many Yes buckets (e.g. F1 podium).
            # Never fall back to pick-one ``resolved_outcome`` comparison.
            return None
        outcome_matches = sub_resolved_yes
    else:
        outcome_matches = prediction.predicted_outcome.lower() == market.resolved_outcome.lower()

    if prediction.predicted_direction == Prediction.Direction.YES:
        return outcome_matches
    return not outcome_matches


def repair_misscored_multi_binary_predictions(*, dry_run=False):
    """Rescore resolved multi-binary forecasts that used pick-one logic."""
    from markets.forecast_modes import ForecastMode, get_forecast_mode
    from markets.models import Market
    from reputation.services import rescore_resolved_prediction

    rescored = []
    for market in Market.objects.filter(status=Market.Status.RESOLVED).iterator():
        if get_forecast_mode(market) != ForecastMode.MULTI_BINARY:
            continue
        event = market.polymarket_event_raw or {}
        if not event.get("markets"):
            continue
        for prediction in Prediction.objects.filter(
            market=market,
            status=Prediction.Status.RESOLVED,
        ).select_related("user", "user__profile"):
            expected = prediction_is_correct_for_resolved_market(market, prediction)
            if expected is None or prediction.is_correct == expected:
                continue
            if dry_run:
                rescored.append(
                    {
                        "prediction_id": prediction.id,
                        "username": prediction.user.username,
                        "market_slug": market.polymarket_slug,
                        "was_correct": prediction.is_correct,
                        "should_be_correct": expected,
                    }
                )
                continue
            rescore_resolved_prediction(prediction, is_correct=expected)
            from predictions.incident_notice_services import (
                is_f1_podium_leclerc_prediction,
                notify_f1_podium_incident_rescore,
            )

            if is_f1_podium_leclerc_prediction(prediction):
                notify_f1_podium_incident_rescore(
                    user_id=prediction.user_id,
                    prediction_id=prediction.id,
                )
            rescored.append(prediction.id)

    return rescored


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
        is_correct = prediction_is_correct_for_resolved_market(market, prediction)
        if is_correct is None:
            continue
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
