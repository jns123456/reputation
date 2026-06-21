"""Reputation scoring services."""

from django.conf import settings
from django.db import IntegrityError, transaction

from reputation.models import ReputationEvent


def calculate_reputation_score(*, reputation_points, scored_forecast_count):
    """Ranking score: average reputation P&L per scored forecast.

    ``reputation_points`` stays the cumulative total shown in the UI.
    ``reputation_score`` drives leaderboards and content tie-breaking.

    Uses ``max(scored_forecast_count, REPUTATION_SCORE_MIN_SAMPLE)`` so a single
    lucky forecast cannot dominate users with sustained track records.
    """
    if scored_forecast_count <= 0:
        return 0.0
    min_sample = max(1, int(getattr(settings, "REPUTATION_SCORE_MIN_SAMPLE", 3)))
    effective_count = max(scored_forecast_count, min_sample)
    return round(float(reputation_points) / effective_count, 2)


def refresh_profile_reputation_score(profile, *, save=True):
    """Recompute ``reputation_score`` from stored aggregates."""
    profile.reputation_score = calculate_reputation_score(
        reputation_points=profile.reputation_points,
        scored_forecast_count=profile.scored_forecast_count,
    )
    if save:
        profile.save(update_fields=["reputation_score", "updated_at"])
    return profile.reputation_score


def refresh_category_reputation_score(stats, *, save=True):
    """Recompute category ``reputation_score`` from stored aggregates."""
    stats.reputation_score = calculate_reputation_score(
        reputation_points=stats.reputation_points,
        scored_forecast_count=stats.scored_forecast_count,
    )
    if save:
        stats.save(update_fields=["reputation_score", "updated_at"])
    return stats.reputation_score


def get_predicted_outcome_probability(predicted_outcome, probability_snapshot, predicted_direction="yes"):
    """Return market probability (0–1) for the user's chosen outcome at forecast time."""
    if not probability_snapshot:
        return 0.5

    prob = probability_snapshot.get(predicted_outcome)
    if prob is None:
        for key, value in probability_snapshot.items():
            if key.lower() == predicted_outcome.lower():
                prob = value
                break

    if prob is None:
        # Missing outcome with other prices present usually means that bucket closed
        # (e.g. eliminated player removed from open-only sync) — treat as 0, not 50%.
        if probability_snapshot:
            return 0.0
        return 0.5

    probability = max(0.0, min(1.0, float(prob)))
    if str(predicted_direction).lower() == "no":
        return 1.0 - probability
    return probability


def calculate_reputation_stakes(*, predicted_outcome, probability_snapshot, predicted_direction="yes"):
    """
    Points at stake from Polymarket odds at forecast time.

    Correct: 100 − market_probability_percent
    Incorrect: −market_probability_percent

    Example: Yes at 90% → win +10, lose −90.
    """
    prob_percent = int(
        round(
            get_predicted_outcome_probability(
                predicted_outcome,
                probability_snapshot,
                predicted_direction=predicted_direction,
            )
            * 100
        )
    )
    return {
        "prob_percent": prob_percent,
        "win_points": 100 - prob_percent,
        "loss_points": prob_percent,
    }


def calculate_reputation_delta(*, is_correct, predicted_outcome, probability_snapshot, predicted_direction="yes"):
    stakes = calculate_reputation_stakes(
        predicted_outcome=predicted_outcome,
        probability_snapshot=probability_snapshot,
        predicted_direction=predicted_direction,
    )
    if is_correct:
        return stakes["win_points"]
    return -stakes["loss_points"]


def calculate_exit_reputation_delta(
    *,
    predicted_outcome,
    entry_probability_snapshot,
    exit_probability_snapshot,
    predicted_direction="yes",
):
    """Reputation P&L from closing a forecast before market resolution."""
    entry_probability = get_predicted_outcome_probability(
        predicted_outcome,
        entry_probability_snapshot,
        predicted_direction=predicted_direction,
    )
    exit_probability = get_predicted_outcome_probability(
        predicted_outcome,
        exit_probability_snapshot,
        predicted_direction=predicted_direction,
    )
    return int(round((exit_probability - entry_probability) * 100))


def calculate_unrealized_reputation(prediction, *, current_probability=None):
    """Mark-to-market reputation P&L for an OPEN forecast at live odds.

    Same math as an exit, but using current market odds instead of an exit
    snapshot. Computed on the fly and never persisted, so it cannot touch the
    immutable record of resolved/exited predictions (AGENTS.md §6).

    Returns the signed reputation delta the user would realize by exiting now,
    or ``None`` if the forecast is not open.
    """
    if prediction.status != prediction.Status.PENDING:
        return None
    snapshot = current_probability
    if snapshot is None:
        snapshot = getattr(prediction.market, "current_probability", None) or {}
    if not snapshot:
        return None
    return calculate_exit_reputation_delta(
        predicted_outcome=prediction.predicted_outcome,
        entry_probability_snapshot=prediction.probability_at_prediction_time,
        exit_probability_snapshot=snapshot,
        predicted_direction=prediction.predicted_direction,
    )


def calculate_user_unrealized_reputation(user, *, limit=100):
    """Sum mark-to-market reputation P&L across the user's open forecasts."""
    from predictions.selectors import get_user_open_predictions

    total = 0
    for prediction in get_user_open_predictions(user, limit=limit):
        delta = calculate_unrealized_reputation(prediction)
        if delta is not None:
            total += delta
    return total


def exit_delta_counts_as_correct(delta):
    """Map early-exit P&L to win/loss for aggregate accuracy stats."""
    if delta > 0:
        return True
    if delta < 0:
        return False
    return None


def apply_reputation_for_prediction_exit(prediction):
    """Apply reputation scoring when a user exits an active prediction."""
    if prediction.status != prediction.Status.EXITED:
        return None

    if ReputationEvent.objects.filter(
        prediction=prediction,
        event_type=ReputationEvent.EventType.EXITED_PREDICTION,
    ).exists():
        return None

    delta = calculate_exit_reputation_delta(
        predicted_outcome=prediction.predicted_outcome,
        entry_probability_snapshot=prediction.probability_at_prediction_time,
        exit_probability_snapshot=prediction.probability_at_exit_time,
        predicted_direction=prediction.predicted_direction,
    )
    entry_percent = int(
        round(
            get_predicted_outcome_probability(
                prediction.predicted_outcome,
                prediction.probability_at_prediction_time,
                predicted_direction=prediction.predicted_direction,
            )
            * 100
        )
    )
    exit_percent = int(
        round(
            get_predicted_outcome_probability(
                prediction.predicted_outcome,
                prediction.probability_at_exit_time,
                predicted_direction=prediction.predicted_direction,
            )
            * 100
        )
    )
    reason = (
        f"Forecast on '{prediction.market.title}' was exited "
        f"(forecast: {prediction.get_predicted_direction_display()} {prediction.predicted_outcome}, "
        f"entry probability {entry_percent}%, exit probability {exit_percent}%, "
        f"{'+' if delta >= 0 else ''}{delta} reputation)."
    )

    try:
        event = ReputationEvent.objects.create(
            user=prediction.user,
            prediction=prediction,
            event_type=ReputationEvent.EventType.EXITED_PREDICTION,
            points_delta=delta,
            reason=reason,
        )
    except IntegrityError:
        return None

    from integrations.attestation_services import record_reputation_event_attestation_safely

    record_reputation_event_attestation_safely(event)

    profile = prediction.user.profile
    profile.reputation_points += delta
    profile.scored_forecast_count += 1
    exit_is_correct = exit_delta_counts_as_correct(delta)
    update_fields = [
        "reputation_points",
        "scored_forecast_count",
        "reputation_score",
        "updated_at",
    ]
    if exit_is_correct is True:
        profile.correct_prediction_count += 1
        update_fields.append("correct_prediction_count")
    elif exit_is_correct is False:
        profile.incorrect_prediction_count += 1
        update_fields.append("incorrect_prediction_count")
    refresh_profile_reputation_score(profile, save=False)
    profile.save(update_fields=update_fields)

    from accounts.category_stats_services import (
        apply_category_reputation_delta,
        resolve_category_from_market,
    )

    apply_category_reputation_delta(
        prediction.user,
        resolve_category_from_market(prediction.market),
        delta,
        is_correct=exit_is_correct,
    )

    from accounts.achievement_services import evaluate_achievements

    evaluate_achievements(prediction.user)

    return event


def rescore_resolved_prediction(prediction, *, is_correct):
    """Replace a prior resolution score when ``is_correct`` was wrong."""
    from accounts.models import UserCategoryStats, UserProfile
    from accounts.category_stats_services import resolve_category_from_market

    if prediction.status != prediction.Status.RESOLVED:
        raise ValueError("Only resolved predictions can be rescored.")

    old_event = prediction.reputation_events.filter(
        event_type__in=[
            ReputationEvent.EventType.CORRECT_PREDICTION,
            ReputationEvent.EventType.INCORRECT_PREDICTION,
        ]
    ).first()
    if prediction.is_correct == is_correct and old_event:
        expected_delta = calculate_reputation_delta(
            is_correct=is_correct,
            predicted_outcome=prediction.predicted_outcome,
            probability_snapshot=prediction.probability_at_prediction_time,
            predicted_direction=prediction.predicted_direction,
        )
        if old_event.points_delta == expected_delta:
            return prediction

    with transaction.atomic():
        if old_event:
            profile = UserProfile.objects.select_for_update().get(user=prediction.user)
            profile.reputation_points -= old_event.points_delta
            profile.scored_forecast_count = max(0, profile.scored_forecast_count - 1)
            old_was_correct = (
                old_event.event_type == ReputationEvent.EventType.CORRECT_PREDICTION
            )
            if old_was_correct:
                profile.correct_prediction_count = max(
                    0, profile.correct_prediction_count - 1
                )
            else:
                profile.incorrect_prediction_count = max(
                    0, profile.incorrect_prediction_count - 1
                )
            refresh_profile_reputation_score(profile, save=False)
            profile.save(
                update_fields=[
                    "reputation_points",
                    "scored_forecast_count",
                    "correct_prediction_count",
                    "incorrect_prediction_count",
                    "reputation_score",
                    "updated_at",
                ]
            )

            category_slug = resolve_category_from_market(prediction.market)
            stats = UserCategoryStats.objects.select_for_update().filter(
                user=prediction.user,
                category_slug=category_slug,
            ).first()
            if stats:
                stats.reputation_points -= old_event.points_delta
                stats.scored_forecast_count = max(0, stats.scored_forecast_count - 1)
                if old_was_correct:
                    stats.correct_prediction_count = max(
                        0, stats.correct_prediction_count - 1
                    )
                else:
                    stats.incorrect_prediction_count = max(
                        0, stats.incorrect_prediction_count - 1
                    )
                refresh_category_reputation_score(stats, save=False)
                stats.save(
                    update_fields=[
                        "reputation_points",
                        "scored_forecast_count",
                        "correct_prediction_count",
                        "incorrect_prediction_count",
                        "reputation_score",
                        "updated_at",
                    ]
                )

            old_event.delete()

        prediction.is_correct = is_correct
        prediction.save(update_fields=["is_correct", "updated_at"])
        prediction.user.profile.refresh_from_db()
        apply_reputation_for_prediction(prediction)

    from accounts.achievement_services import evaluate_achievements

    evaluate_achievements(prediction.user)
    return prediction


def apply_reputation_for_prediction(prediction):
    """Apply reputation scoring when a prediction is resolved."""
    if prediction.status != prediction.Status.RESOLVED:
        return None

    if ReputationEvent.objects.filter(
        prediction=prediction,
        event_type__in=[
            ReputationEvent.EventType.CORRECT_PREDICTION,
            ReputationEvent.EventType.INCORRECT_PREDICTION,
        ],
    ).exists():
        return None

    is_correct = prediction.is_correct
    if is_correct is None:
        return None

    stakes = calculate_reputation_stakes(
        predicted_outcome=prediction.predicted_outcome,
        probability_snapshot=prediction.probability_at_prediction_time,
        predicted_direction=prediction.predicted_direction,
    )
    delta = calculate_reputation_delta(
        is_correct=is_correct,
        predicted_outcome=prediction.predicted_outcome,
        probability_snapshot=prediction.probability_at_prediction_time,
        predicted_direction=prediction.predicted_direction,
    )

    event_type = (
        ReputationEvent.EventType.CORRECT_PREDICTION
        if is_correct
        else ReputationEvent.EventType.INCORRECT_PREDICTION
    )

    reason = (
        f"Forecast on '{prediction.market.title}' was "
        f"{'correct' if is_correct else 'incorrect'} "
        f"(forecast: {prediction.get_predicted_direction_display()} {prediction.predicted_outcome}, "
        f"Polymarket was {stakes['prob_percent']}% at forecast time, "
        f"{'+' if delta >= 0 else ''}{delta} reputation)."
    )

    try:
        event = ReputationEvent.objects.create(
            user=prediction.user,
            prediction=prediction,
            event_type=event_type,
            points_delta=delta,
            reason=reason,
        )
    except IntegrityError:
        return None

    from integrations.attestation_services import record_reputation_event_attestation_safely

    record_reputation_event_attestation_safely(event)

    profile = prediction.user.profile
    profile.reputation_points += delta
    profile.scored_forecast_count += 1
    if is_correct:
        profile.correct_prediction_count += 1
    else:
        profile.incorrect_prediction_count += 1
    refresh_profile_reputation_score(profile, save=False)
    profile.save(
        update_fields=[
            "reputation_points",
            "scored_forecast_count",
            "correct_prediction_count",
            "incorrect_prediction_count",
            "reputation_score",
            "updated_at",
        ]
    )

    from accounts.category_stats_services import (
        apply_category_reputation_delta,
        resolve_category_from_market,
    )

    apply_category_reputation_delta(
        prediction.user,
        resolve_category_from_market(prediction.market),
        delta,
        is_correct=is_correct,
    )

    from accounts.notification_services import notify_prediction_resolved

    notify_prediction_resolved(prediction=prediction, reputation_event=event)

    # Re-check accuracy-based achievements (e.g. first correct, sharp eye).
    from accounts.achievement_services import evaluate_achievements

    evaluate_achievements(prediction.user)

    return event
