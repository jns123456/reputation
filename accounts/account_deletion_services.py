"""Permanent account deletion — removes the user and all related platform data."""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets

from django.core.cache import cache
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from accounts.models import User

logger = logging.getLogger(__name__)

# Re-auth for password-less (OAuth) accounts: a short-lived emailed code must be
# confirmed before deletion, so a stolen session alone cannot destroy the account.
DELETION_CODE_TTL_SECONDS = 15 * 60
DELETION_CODE_RESEND_COOLDOWN_SECONDS = 60


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


def deletion_requires_email_code(user: User) -> bool:
    """OAuth/password-less accounts re-authenticate via an emailed code."""
    return not user.has_usable_password()


def _deletion_code_cache_key(user: User) -> str:
    return f"account_deletion_code:{user.pk}"


def _hash_deletion_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def send_deletion_confirmation_code(user: User) -> tuple[bool, str]:
    """Email a one-time confirmation code; returns (sent, user_message)."""
    from accounts.email_services import EmailDeliveryError, _send

    if not user.email:
        return False, str(_("Add an email address to your profile first."))

    cooldown_key = f"{_deletion_code_cache_key(user)}:cooldown"
    if cache.get(cooldown_key):
        return False, str(_("Please wait a minute before requesting another code."))

    code = f"{secrets.randbelow(1_000_000):06d}"
    cache.set(_deletion_code_cache_key(user), _hash_deletion_code(code), DELETION_CODE_TTL_SECONDS)

    try:
        sent = _send(
            subject=lambda: _("Confirm your PredictStamp account deletion"),
            recipient_email=user.email,
            template_base="account_deletion_code",
            context={
                "recipient": user,
                "code": code,
                "expires_minutes": DELETION_CODE_TTL_SECONDS // 60,
            },
        )
    except EmailDeliveryError as exc:
        logger.warning("Deletion code email failed for user_id=%s: %s", user.pk, exc)
        cache.delete(_deletion_code_cache_key(user))
        return False, str(_("We couldn't send the confirmation email. Try again later."))

    if not sent:
        cache.delete(_deletion_code_cache_key(user))
        return False, str(_("We couldn't send the confirmation email. Try again later."))

    cache.set(cooldown_key, True, DELETION_CODE_RESEND_COOLDOWN_SECONDS)
    return True, str(_("We emailed you a confirmation code. It expires in 15 minutes."))


def verify_deletion_confirmation_code(user: User, code: str) -> bool:
    """Check (and consume) the emailed confirmation code."""
    stored = cache.get(_deletion_code_cache_key(user))
    if not stored or not code:
        return False
    if not hmac.compare_digest(stored, _hash_deletion_code(code.strip())):
        return False
    cache.delete(_deletion_code_cache_key(user))
    return True


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
