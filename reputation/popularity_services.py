"""Popularity scoring services."""

from django.conf import settings
from django.core.cache import cache

from reputation.models import PopularityEvent

# Shares feed POPULARITY only (never reputation, §6) and are tightly capped so
# the share button cannot become an engagement-farming vector.
SHARE_POINTS = 1
SHARE_DEDUPE_SECONDS = 60 * 60 * 24 * 30
SHARE_DAILY_OWNER_CAP = 20


def record_popularity_event(
    *,
    user,
    points_delta,
    event_type,
    reason,
    comment=None,
    prediction=None,
    pulse_post=None,
    pulse_comment=None,
):
    event = PopularityEvent.objects.create(
        user=user,
        comment=comment,
        prediction=prediction,
        pulse_post=pulse_post,
        pulse_comment=pulse_comment,
        event_type=event_type,
        points_delta=points_delta,
        reason=reason,
    )
    profile = user.profile
    profile.popularity_points += points_delta
    profile.popularity_score = float(profile.popularity_points)
    profile.save(update_fields=["popularity_points", "popularity_score", "updated_at"])

    from accounts.category_stats_services import (
        apply_category_popularity_delta,
        resolve_category_from_popularity_event,
    )

    category_slug = resolve_category_from_popularity_event(
        comment=comment,
        prediction=prediction,
        pulse_post=pulse_post,
        pulse_comment=pulse_comment,
    )
    if category_slug is not None:
        apply_category_popularity_delta(user, category_slug, points_delta)

    from accounts.achievement_services import evaluate_achievements

    evaluate_achievements(user)

    return event


def record_prediction_share(*, prediction, viewer):
    """Award a small popularity bonus when someone shares a forecast card.

    Deduped per (viewer, prediction) and capped per owner per day so repeated
    clicks or coordinated sharing cannot farm popularity. Anonymous viewers and
    self-shares never award points.
    """
    if viewer is None or not viewer.is_authenticated:
        return None
    if viewer.id == prediction.user_id:
        return None

    dedupe_key = f"share-dedupe:{viewer.id}:{prediction.id}"
    if not cache.add(dedupe_key, 1, SHARE_DEDUPE_SECONDS):
        return None

    from django.utils import timezone

    cap_key = f"share-owner-cap:{prediction.user_id}:{timezone.localdate().isoformat()}"
    try:
        daily_total = cache.incr(cap_key)
    except ValueError:
        cache.add(cap_key, 1, 60 * 60 * 24)
        daily_total = 1
    if daily_total > SHARE_DAILY_OWNER_CAP:
        return None

    event = record_popularity_event(
        user=prediction.user,
        points_delta=SHARE_POINTS,
        event_type=PopularityEvent.EventType.SHARE_RECEIVED,
        reason=f"Forecast shared by {viewer.username}",
        prediction=prediction,
    )

    prediction.popularity_score = (prediction.popularity_score or 0) + SHARE_POINTS
    prediction.save(update_fields=["popularity_score", "updated_at"])
    return event


def apply_vote_popularity(*, content_owner, target, target_type, old_value, new_value, voter):
    """Update popularity when a vote is cast or changed."""
    from comments.models import Vote

    upvote_pts = settings.POPULARITY_UPVOTE_POINTS
    downvote_pts = settings.POPULARITY_DOWNVOTE_POINTS

    delta = 0
    if old_value is None:
        delta = upvote_pts if new_value > 0 else downvote_pts
    elif new_value == 0:
        delta = -upvote_pts if old_value > 0 else -downvote_pts
    elif old_value != new_value:
        delta = (upvote_pts - downvote_pts) if new_value > 0 else (downvote_pts - upvote_pts)

    if delta == 0:
        return None

    event_type = (
        PopularityEvent.EventType.UPVOTE_RECEIVED
        if delta > 0
        else PopularityEvent.EventType.DOWNVOTE_RECEIVED
    )

    comment = target if target_type == Vote.TargetType.COMMENT else None
    prediction = target if target_type == Vote.TargetType.PREDICTION else None
    pulse_post = target if target_type == Vote.TargetType.PULSE_POST else None
    pulse_comment = target if target_type == Vote.TargetType.PULSE_COMMENT else None

    record_popularity_event(
        user=content_owner,
        points_delta=delta,
        event_type=event_type,
        reason=f"Vote change on {target_type} by {voter.username}",
        comment=comment,
        prediction=prediction,
        pulse_post=pulse_post,
        pulse_comment=pulse_comment,
    )

    if hasattr(target, "popularity_score"):
        target.popularity_score = (target.popularity_score or 0) + delta
        target.save(update_fields=["popularity_score", "updated_at"])

    return delta
