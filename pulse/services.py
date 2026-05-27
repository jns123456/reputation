"""Pulse post and comment business logic."""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from pulse.models import Comment, Poll, PollOption, PollVote, Post
from reputation.models import PopularityEvent
from reputation.popularity_services import record_popularity_event


def create_post(*, user, body="", image=None, poll_payload=None):
    if poll_payload and image:
        raise ValueError(_("Polls can't include images."))

    with transaction.atomic():
        post = Post(user=user, body=body)
        if image:
            post.image = image
        post.save()
        if poll_payload:
            _create_poll_for_post(
                post=post,
                options=poll_payload["options"],
                duration_days=poll_payload["duration_days"],
            )
        record_popularity_event(
            user=user,
            points_delta=0,
            event_type=PopularityEvent.EventType.POST_PUBLISHED,
            reason="Published a Forum post",
            pulse_post=post,
        )
    return post


def _create_poll_for_post(*, post, options, duration_days):
    poll = Poll.objects.create(
        post=post,
        ends_at=timezone.now() + timedelta(days=duration_days),
    )
    PollOption.objects.bulk_create(
        [
            PollOption(poll=poll, text=text, position=index)
            for index, text in enumerate(options)
        ]
    )
    return poll


def vote_on_poll(*, user, poll, option):
    if poll.is_closed:
        raise ValueError(_("This poll has ended."))

    if option.poll_id != poll.id:
        raise ValueError(_("Invalid poll choice."))

    if poll.post.user_id == user.id:
        raise ValueError(_("You can't vote on your own poll."))

    with transaction.atomic():
        vote, created = PollVote.objects.update_or_create(
            user=user,
            poll=poll,
            defaults={"option": option},
        )
    return vote, created


def toggle_repost(*, user, post):
    """Create or remove a repost of another user's Forum post."""
    original = resolve_original_post(post)
    if original.user_id == user.id:
        raise ValueError(_("You cannot repost your own post."))

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


def _delete_owned_post(*, post):
    from accounts.models import Bookmark
    from comments.models import Vote

    comment_ids = list(post.comments.values_list("id", flat=True))
    with transaction.atomic():
        Vote.objects.filter(
            target_type=Vote.TargetType.PULSE_POST,
            target_id=post.id,
        ).delete()
        if comment_ids:
            Vote.objects.filter(
                target_type=Vote.TargetType.PULSE_COMMENT,
                target_id__in=comment_ids,
            ).delete()
        Bookmark.objects.filter(
            target_type=Bookmark.TargetType.PULSE_POST,
            target_id=post.id,
        ).delete()
        if hasattr(post, "poll"):
            try:
                post.poll.delete()
            except Poll.DoesNotExist:
                pass
        post.delete()


def delete_post(*, user, post):
    if post.user_id != user.id:
        raise ValueError(_("You can only delete your own posts."))

    if post.reposted_from_id:
        _remove_repost(repost=post, original=post.reposted_from)
        return

    _delete_owned_post(post=post)


def create_pulse_comment(*, user, post, body, parent_comment=None):
    if parent_comment:
        if parent_comment.post_id != post.id:
            raise ValueError(_("Parent comment belongs to a different post."))

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


def _collect_comment_descendant_ids(comment):
    ids = [comment.id]
    for reply in comment.replies.all():
        ids.extend(_collect_comment_descendant_ids(reply))
    return ids


def delete_pulse_comment(*, user, comment):
    from comments.models import Vote

    if comment.user_id != user.id:
        raise ValueError(_("You can only delete your own comments."))

    comment_ids = _collect_comment_descendant_ids(comment)
    with transaction.atomic():
        Vote.objects.filter(
            target_type=Vote.TargetType.PULSE_COMMENT,
            target_id__in=comment_ids,
        ).delete()
        comment.delete()


def _assert_can_comment_on_post(*, user, post, parent_comment=None):
    if user != post.user:
        return
    if parent_comment is None:
        raise ValueError(_("You cannot comment on your own post. Reply to others instead."))
    if parent_comment.user == user:
        raise ValueError(_("You cannot reply to your own comment."))