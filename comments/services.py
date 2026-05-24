"""Comment and vote services."""

from django.db import transaction

from comments.models import Comment, Vote
from reputation.models import PopularityEvent
from reputation.popularity_services import apply_vote_popularity, record_popularity_event


def create_comment(*, user, market, body, parent_comment=None, prediction=None):
    if parent_comment:
        if parent_comment.market_id != market.id:
            raise ValueError("Parent comment belongs to a different market.")
        if prediction and parent_comment.prediction_id != prediction.id:
            raise ValueError("Parent comment belongs to a different forecast thread.")
        if not prediction:
            prediction = parent_comment.prediction

    if prediction and prediction.market_id != market.id:
        raise ValueError("Prediction belongs to a different market.")

    _assert_can_comment_on_prediction(
        user=user,
        prediction=prediction,
        parent_comment=parent_comment,
    )

    with transaction.atomic():
        comment = Comment.objects.create(
            user=user,
            market=market,
            prediction=prediction,
            body=body,
            parent_comment=parent_comment,
        )
        record_popularity_event(
            user=user,
            points_delta=0,
            event_type=PopularityEvent.EventType.COMMENT_POSTED,
            reason=f"Posted comment on {market.title}",
            comment=comment,
        )
        if parent_comment:
            record_popularity_event(
                user=parent_comment.user,
                points_delta=1,
                event_type=PopularityEvent.EventType.REPLY_RECEIVED,
                reason=f"Received reply from {user.username}",
                comment=parent_comment,
            )
            parent_comment.popularity_score += 1
            parent_comment.save(update_fields=["popularity_score", "updated_at"])
    return comment


def cast_vote(*, user, target_type, target_id, value):
    """Cast or update a vote. Value: 1 (upvote), -1 (downvote), 0 (remove)."""
    target = _get_vote_target(target_type, target_id)
    if target is None:
        raise ValueError("Vote target not found.")

    content_owner = target.user
    if content_owner == user:
        if target_type == Vote.TargetType.PREDICTION:
            raise ValueError("You cannot vote on your own forecast.")
        if target_type == Vote.TargetType.PULSE_POST:
            raise ValueError("You cannot vote on your own post.")
        raise ValueError("Cannot vote on your own content.")

    with transaction.atomic():
        vote, created = Vote.objects.get_or_create(
            user=user,
            target_type=target_type,
            target_id=target_id,
            defaults={"value": value},
        )
        old_value = None if created else vote.value

        if value == 0:
            if not created:
                apply_vote_popularity(
                    content_owner=content_owner,
                    target=target,
                    target_type=target_type,
                    old_value=old_value,
                    new_value=0,
                    voter=user,
                )
                vote.delete()
            return None

        if not created:
            if vote.value == value:
                return vote
            vote.value = value
            vote.save(update_fields=["value", "updated_at"])
        else:
            vote.value = value
            vote.save()

        apply_vote_popularity(
            content_owner=content_owner,
            target=target,
            target_type=target_type,
            old_value=old_value,
            new_value=value,
            voter=user,
        )

        from accounts.notification_services import notify_vote_received

        notify_vote_received(
            actor=user,
            recipient=content_owner,
            target=target,
            target_type=target_type,
            value=value,
        )

    return vote


def _assert_can_comment_on_prediction(*, user, prediction, parent_comment=None):
    if prediction is None or user != prediction.user:
        return
    if parent_comment is None:
        raise ValueError(
            "You cannot comment on your own forecast. Reply to others instead."
        )
    if parent_comment.user == user:
        raise ValueError("You cannot reply to your own comment.")


def _get_vote_target(target_type, target_id):
    if target_type == Vote.TargetType.COMMENT:
        return Comment.objects.filter(pk=target_id).select_related("user").first()
    if target_type == Vote.TargetType.PREDICTION:
        from predictions.models import Prediction

        return Prediction.objects.filter(pk=target_id).select_related("user").first()
    if target_type == Vote.TargetType.PULSE_POST:
        from pulse.models import Post

        return Post.objects.filter(pk=target_id).select_related("user").first()
    if target_type == Vote.TargetType.PULSE_COMMENT:
        from pulse.models import Comment as PulseComment

        return PulseComment.objects.filter(pk=target_id).select_related("user").first()
    return None


def get_user_vote(user, target_type, target_id):
    if not user.is_authenticated:
        return None
    return Vote.objects.filter(
        user=user,
        target_type=target_type,
        target_id=target_id,
    ).first()
