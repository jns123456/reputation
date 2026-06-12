"""Rebuild user profile aggregates from immutable reputation event records."""

from collections import defaultdict

from reputation.models import ReputationEvent
from reputation.services import calculate_reputation_score, exit_delta_counts_as_correct

SCORED_REPUTATION_EVENT_TYPES = (
    ReputationEvent.EventType.CORRECT_PREDICTION,
    ReputationEvent.EventType.INCORRECT_PREDICTION,
    ReputationEvent.EventType.EXITED_PREDICTION,
)


def _aggregate_scored_counters(events_qs):
    counters_by_user = defaultdict(
        lambda: {"correct": 0, "incorrect": 0, "scored_prediction_ids": set()}
    )
    for event in events_qs.iterator():
        counters = counters_by_user[event.user_id]
        counters["scored_prediction_ids"].add(event.prediction_id)
        if event.event_type == ReputationEvent.EventType.CORRECT_PREDICTION:
            counters["correct"] += 1
        elif event.event_type == ReputationEvent.EventType.INCORRECT_PREDICTION:
            counters["incorrect"] += 1
        elif event.event_type == ReputationEvent.EventType.EXITED_PREDICTION:
            exit_is_correct = exit_delta_counts_as_correct(event.points_delta)
            if exit_is_correct is True:
                counters["correct"] += 1
            elif exit_is_correct is False:
                counters["incorrect"] += 1
    return counters_by_user


def rebuild_profile_reputation_counters(*, user=None):
    """Recompute leaderboard counters from scored reputation events (idempotent).

    Includes resolved and early-exited forecasts. Safe to re-run after deploy.
    """
    from accounts.models import UserProfile

    events_qs = ReputationEvent.objects.filter(
        event_type__in=SCORED_REPUTATION_EVENT_TYPES,
    )
    profiles_qs = UserProfile.objects.all()
    if user is not None:
        events_qs = events_qs.filter(user=user)
        profiles_qs = profiles_qs.filter(user=user)

    counters_by_user = _aggregate_scored_counters(events_qs)
    updated = 0

    for profile in profiles_qs.iterator():
        counters = counters_by_user.get(profile.user_id)
        if counters is None:
            if (
                profile.scored_forecast_count == 0
                and profile.correct_prediction_count == 0
                and profile.incorrect_prediction_count == 0
            ):
                continue
            scored = 0
            correct = 0
            incorrect = 0
        else:
            scored = len(counters["scored_prediction_ids"])
            correct = counters["correct"]
            incorrect = counters["incorrect"]

        reputation_score = calculate_reputation_score(
            reputation_points=profile.reputation_points,
            scored_forecast_count=scored,
        )

        if (
            profile.scored_forecast_count == scored
            and profile.correct_prediction_count == correct
            and profile.incorrect_prediction_count == incorrect
            and profile.reputation_score == reputation_score
        ):
            continue

        profile.scored_forecast_count = scored
        profile.correct_prediction_count = correct
        profile.incorrect_prediction_count = incorrect
        profile.reputation_score = reputation_score
        profile.save(
            update_fields=[
                "scored_forecast_count",
                "correct_prediction_count",
                "incorrect_prediction_count",
                "reputation_score",
                "updated_at",
            ]
        )
        updated += 1

    return updated
