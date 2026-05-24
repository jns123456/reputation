"""Pulse post and comment business logic."""

from django.conf import settings
from django.db import transaction

from pulse.models import Comment, Post
from reputation.models import PopularityEvent
from reputation.popularity_services import record_popularity_event


def create_post(*, user, body="", image=None):
    with transaction.atomic():
        post = Post(user=user, body=body)
        if image:
            post.image = image
        post.save()
        record_popularity_event(
            user=user,
            points_delta=0,
            event_type=PopularityEvent.EventType.POST_PUBLISHED,
            reason="Published a Forum post",
            pulse_post=post,
        )
    return post


def toggle_repost(*, user, post):
    """Create or remove a repost of another user's Forum post."""
    original = resolve_original_post(post)
    if original.user_id == user.id:
        raise ValueError("You cannot repost your own post.")

    existing = Post.objects.filter(user=user, reposted_from=original).first()
    if existing:
        return _remove_repost(repost=existing, original=original)

    return _create_repost(user=user, original=original)


def resolve_original_post(post):
    return post.original_post


def _create_repost(*, user, original):
    repost_points = settings.POPULARITY_REPOST_POINTS
    with transaction.atomic():
        repost = Post.objects.create(user=user, reposted_from=original)
        record_popularity_event(
            user=original.user,
            points_delta=repost_points,
            event_type=PopularityEvent.EventType.REPOST_RECEIVED,
            reason=f"Reposted by {user.username}",
            pulse_post=original,
        )
        original.popularity_score += repost_points
        original.save(update_fields=["popularity_score", "updated_at"])
    return repost, True


def _remove_repost(*, repost, original):
    repost_points = settings.POPULARITY_REPOST_POINTS
    repost_id = repost.id
    with transaction.atomic():
        record_popularity_event(
            user=original.user,
            points_delta=-repost_points,
            event_type=PopularityEvent.EventType.REPOST_RECEIVED,
            reason=f"Repost removed by {repost.user.username}",
            pulse_post=original,
        )
        original.popularity_score -= repost_points
        original.save(update_fields=["popularity_score", "updated_at"])
        repost.delete()
    return repost_id, False


def create_pulse_comment(*, user, post, body, parent_comment=None):
    if parent_comment:
        if parent_comment.post_id != post.id:
            raise ValueError("Parent comment belongs to a different post.")

    _assert_can_comment_on_post(user=user, post=post, parent_comment=parent_comment)

    with transaction.atomic():
        comment = Comment.objects.create(
            user=user,
            post=post,
            body=body,
            parent_comment=parent_comment,
        )
        record_popularity_event(
            user=user,
            points_delta=0,
            event_type=PopularityEvent.EventType.COMMENT_POSTED,
            reason=f"Commented on Forum post {post.id}",
            pulse_comment=comment,
        )
        if parent_comment:
            record_popularity_event(
                user=parent_comment.user,
                points_delta=1,
                event_type=PopularityEvent.EventType.REPLY_RECEIVED,
                reason=f"Received reply from {user.username}",
                pulse_comment=parent_comment,
            )
            parent_comment.popularity_score += 1
            parent_comment.save(update_fields=["popularity_score", "updated_at"])
    return comment


def _assert_can_comment_on_post(*, user, post, parent_comment=None):
    if user != post.user:
        return
    if parent_comment is None:
        raise ValueError("You cannot comment on your own post. Reply to others instead.")
    if parent_comment.user == user:
        raise ValueError("You cannot reply to your own comment.")