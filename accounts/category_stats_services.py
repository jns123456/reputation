"""Per-category reputation and popularity aggregate updates."""

from accounts.models import UserCategoryStats
from markets.categories import resolve_market_category_slug


def resolve_category_from_market(market) -> str:
    return resolve_market_category_slug(market)


def resolve_category_from_popularity_event(
    *,
    comment=None,
    prediction=None,
    pulse_post=None,
    pulse_comment=None,
) -> str | None:
    if comment is not None:
        return resolve_category_from_market(comment.market)
    if prediction is not None:
        return resolve_category_from_market(prediction.market)
    return None


def _get_or_create_stats(user, category_slug) -> UserCategoryStats:
    stats, _ = UserCategoryStats.objects.get_or_create(
        user=user,
        category_slug=category_slug,
    )
    return stats


def apply_category_reputation_delta(
    user,
    category_slug,
    delta,
    *,
    is_correct=None,
):
    stats = _get_or_create_stats(user, category_slug)
    stats.reputation_points += delta
    stats.reputation_score = float(stats.reputation_points)
    update_fields = ["reputation_points", "reputation_score", "updated_at"]
    if is_correct is True:
        stats.correct_prediction_count += 1
        update_fields.append("correct_prediction_count")
    elif is_correct is False:
        stats.incorrect_prediction_count += 1
        update_fields.append("incorrect_prediction_count")
    stats.save(update_fields=update_fields)
    return stats


def apply_category_popularity_delta(user, category_slug, delta):
    if delta == 0:
        return None
    stats = _get_or_create_stats(user, category_slug)
    stats.popularity_points += delta
    stats.popularity_score = float(stats.popularity_points)
    stats.save(update_fields=["popularity_points", "popularity_score", "updated_at"])
    return stats


def apply_category_prediction_created(user, category_slug):
    stats = _get_or_create_stats(user, category_slug)
    stats.prediction_count += 1
    stats.save(update_fields=["prediction_count", "updated_at"])
    return stats


def rebuild_all_category_stats():
    """Rebuild per-category aggregates from immutable event records."""
    from predictions.models import Prediction
    from reputation.models import PopularityEvent, ReputationEvent

    UserCategoryStats.objects.all().delete()

    for prediction in Prediction.objects.exclude(status=Prediction.Status.VOID).select_related(
        "market", "user"
    ):
        category_slug = resolve_category_from_market(prediction.market)
        apply_category_prediction_created(prediction.user, category_slug)

    for event in ReputationEvent.objects.filter(
        event_type__in=[
            ReputationEvent.EventType.CORRECT_PREDICTION,
            ReputationEvent.EventType.INCORRECT_PREDICTION,
            ReputationEvent.EventType.EXITED_PREDICTION,
        ],
    ).select_related("prediction__market", "user"):
        category_slug = resolve_category_from_market(event.prediction.market)
        is_correct = None
        if event.event_type == ReputationEvent.EventType.CORRECT_PREDICTION:
            is_correct = True
        elif event.event_type == ReputationEvent.EventType.INCORRECT_PREDICTION:
            is_correct = False
        apply_category_reputation_delta(
            event.user,
            category_slug,
            event.points_delta,
            is_correct=is_correct,
        )

    for event in PopularityEvent.objects.exclude(points_delta=0).select_related(
        "comment__market",
        "prediction__market",
        "user",
    ):
        category_slug = resolve_category_from_popularity_event(
            comment=event.comment,
            prediction=event.prediction,
        )
        if category_slug is None:
            continue
        apply_category_popularity_delta(event.user, category_slug, event.points_delta)
