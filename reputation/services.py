"""Reputation scoring services."""

from reputation.models import ReputationEvent


def get_predicted_outcome_probability(predicted_outcome, probability_snapshot):
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
        return 0.5

    return max(0.0, min(1.0, float(prob)))


def calculate_reputation_stakes(*, predicted_outcome, probability_snapshot):
    """
    Points at stake from Polymarket odds at forecast time.

    Correct: 100 − market_probability_percent
    Incorrect: −market_probability_percent

    Example: Yes at 90% → win +10, lose −90.
    """
    prob_percent = int(round(get_predicted_outcome_probability(predicted_outcome, probability_snapshot) * 100))
    return {
        "prob_percent": prob_percent,
        "win_points": 100 - prob_percent,
        "loss_points": prob_percent,
    }


def calculate_reputation_delta(*, is_correct, predicted_outcome, probability_snapshot):
    stakes = calculate_reputation_stakes(
        predicted_outcome=predicted_outcome,
        probability_snapshot=probability_snapshot,
    )
    if is_correct:
        return stakes["win_points"]
    return -stakes["loss_points"]


def apply_reputation_for_prediction(prediction):
    """Apply reputation scoring when a prediction is resolved."""
    from accounts.models import UserProfile

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
    )
    delta = calculate_reputation_delta(
        is_correct=is_correct,
        predicted_outcome=prediction.predicted_outcome,
        probability_snapshot=prediction.probability_at_prediction_time,
    )

    event_type = (
        ReputationEvent.EventType.CORRECT_PREDICTION
        if is_correct
        else ReputationEvent.EventType.INCORRECT_PREDICTION
    )

    reason = (
        f"Forecast on '{prediction.market.title}' was "
        f"{'correct' if is_correct else 'incorrect'} "
        f"(outcome: {prediction.predicted_outcome}, "
        f"Polymarket was {stakes['prob_percent']}% at forecast time, "
        f"{'+' if delta >= 0 else ''}{delta} reputation)."
    )

    event = ReputationEvent.objects.create(
        user=prediction.user,
        prediction=prediction,
        event_type=event_type,
        points_delta=delta,
        reason=reason,
    )

    profile = prediction.user.profile
    profile.reputation_points += delta
    if is_correct:
        profile.correct_prediction_count += 1
    else:
        profile.incorrect_prediction_count += 1
    profile.reputation_score = float(profile.reputation_points)
    profile.save(
        update_fields=[
            "reputation_points",
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

    return event
