"""Permanent account deletion — removes the user and all related platform data."""

from __future__ import annotations

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from accounts.models import User


class AccountDeletionError(Exception):
    """Raised when an account cannot be deleted."""

    def __init__(self, message, *, code=None):
        self.message = message
        self.code = code
        super().__init__(message)


def can_delete_account(user: User) -> tuple[bool, str]:
    if user.is_superuser:
        return False, str(_("Superuser accounts cannot be deleted from the platform."))
    return True, ""


def delete_user_account(*, user: User) -> int:
    """Delete a user and all related records. Returns the deleted user's pk."""
    allowed, reason = can_delete_account(user)
    if not allowed:
        raise AccountDeletionError(reason, code="not_allowed")

    with transaction.atomic():
        _remove_user_votes_on_others_content(user)
        _remove_votes_on_user_content(user)
        user_id = user.pk
        user.delete()
    return user_id


def _remove_user_votes_on_others_content(user: User) -> None:
    """Reverse popularity from votes the user cast before rows are CASCADE-deleted."""
    from comments.models import Vote
    from comments.services import cast_vote

    for vote in Vote.objects.filter(user=user).iterator():
        try:
            cast_vote(
                user=user,
                target_type=vote.target_type,
                target_id=vote.target_id,
                value=0,
            )
        except ValueError:
            vote.delete()


def _remove_votes_on_user_content(user: User) -> None:
    """Delete votes by others on content owned by this user (generic FK targets)."""
    from comments.models import Comment, Vote
    from predictions.models import Prediction
    from pulse.models import Comment as PulseComment
    from pulse.models import Post

    comment_ids = Comment.objects.filter(user=user).values_list("pk", flat=True)
    if comment_ids:
        Vote.objects.filter(
            target_type=Vote.TargetType.COMMENT,
            target_id__in=comment_ids,
        ).delete()

    prediction_ids = Prediction.objects.filter(user=user).values_list("pk", flat=True)
    if prediction_ids:
        Vote.objects.filter(
            target_type=Vote.TargetType.PREDICTION,
            target_id__in=prediction_ids,
        ).delete()

    post_ids = Post.objects.filter(user=user).values_list("pk", flat=True)
    if post_ids:
        Vote.objects.filter(
            target_type=Vote.TargetType.PULSE_POST,
            target_id__in=post_ids,
        ).delete()

    pulse_comment_ids = PulseComment.objects.filter(user=user).values_list("pk", flat=True)
    if pulse_comment_ids:
        Vote.objects.filter(
            target_type=Vote.TargetType.PULSE_COMMENT,
            target_id__in=pulse_comment_ids,
        ).delete()
