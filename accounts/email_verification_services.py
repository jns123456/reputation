"""Email address verification for new and updated accounts.

Tokens are single-use, time-limited, and tied to the email snapshot at issue time.
Outbound delivery uses Django's email stack (Resend backend when configured).
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from accounts.email_services import absolute_url, EmailDeliveryError
from accounts.models import EmailVerificationToken, User

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailVerificationResult:
    success: bool
    user: User | None = None
    error_code: str = ""
    message: str = ""


def email_verification_required() -> bool:
    return getattr(settings, "EMAIL_VERIFICATION_REQUIRED", True)


def user_requires_email_verification(user: User) -> bool:
    if not email_verification_required():
        return False
    if not user.is_authenticated:
        return False
    if not user.email:
        return True
    return not user.is_email_verified


def _token_ttl() -> timedelta:
    hours = getattr(settings, "EMAIL_VERIFICATION_TOKEN_HOURS", 48)
    return timedelta(hours=hours)


def _resend_cooldown_seconds() -> int:
    return getattr(settings, "EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS", 60)


def _generate_token_value() -> str:
    return secrets.token_urlsafe(32)


def _invalidate_active_tokens(user: User) -> None:
    now = timezone.now()
    EmailVerificationToken.objects.filter(user=user, used_at__isnull=True).update(
        used_at=now,
    )


def _dev_show_verification_link() -> bool:
    return getattr(settings, "EMAIL_VERIFICATION_DEV_SHOW_LINK", settings.DEBUG)


def get_active_verification_url(user: User) -> str | None:
    """Return the latest usable verification URL, if any."""
    token = (
        EmailVerificationToken.objects.filter(
            user=user,
            used_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        .order_by("-created_at")
        .first()
    )
    if token is None:
        return None
    return absolute_url(f"/accounts/verify-email/{token.token}/")


def create_verification_token(user: User) -> EmailVerificationToken:
    """Issue a fresh token; previous unused tokens for the user are invalidated."""
    email = (user.email or "").strip().lower()
    if not email:
        raise ValueError("User has no email address to verify.")

    _invalidate_active_tokens(user)
    return EmailVerificationToken.objects.create(
        user=user,
        token=_generate_token_value(),
        email=email,
        expires_at=timezone.now() + _token_ttl(),
    )


def _send_verification_message(*, user: User, token: EmailVerificationToken) -> bool:
    from accounts.email_services import _send

    verify_url = absolute_url(f"/accounts/verify-email/{token.token}/")
    context = {
        "recipient": user,
        "verify_url": verify_url,
        "expires_hours": int(_token_ttl().total_seconds() // 3600),
        "subject": _("Confirma tu email en PredictStamp"),
    }
    sent = _send(
        subject=context["subject"],
        recipient_email=token.email,
        template_base="email_verification",
        context=context,
    )
    return bool(sent)


def send_verification_email(user: User) -> bool:
    """Create a token and send the confirmation email synchronously."""
    if not user.email:
        logger.warning("Skipping verification email for user_id=%s (no email)", user.pk)
        return False

    from accounts.email_services import _email_delivery_configured

    if not _email_delivery_configured():
        logger.error(
            "No email provider configured (set RESEND_API_KEY or SMTP). "
            "Verification email for user_id=%s was not sent.",
            user.pk,
        )
        raise EmailDeliveryError(
            _(
                "Email sending is not configured yet. Please contact support or try again later."
            ),
            provider="unconfigured",
        )

    token = create_verification_token(user)
    try:
        sent = _send_verification_message(user=user, token=token)
        if not sent:
            raise EmailDeliveryError(
                _("Could not send the verification email."),
                provider="unknown",
            )
        return True
    except EmailDeliveryError:
        if _dev_show_verification_link():
            logger.warning(
                "Verification email not delivered for user_id=%s; dev link is available",
                user.pk,
            )
            return True
        raise


def resend_verification_email(user: User) -> tuple[bool, str]:
    """Resend verification email with a simple per-user cooldown."""
    if user.is_email_verified:
        return False, _("Your email is already verified.")

    if not user.email:
        return False, _("Add an email address to your profile first.")

    cache_key = f"email_verification_resend:{user.pk}"
    if cache.get(cache_key):
        return False, _("Please wait a minute before requesting another email.")

    try:
        send_verification_email(user)
    except EmailDeliveryError as exc:
        logger.warning("Verification resend failed for user_id=%s: %s", user.pk, exc)
        if _dev_show_verification_link() and get_active_verification_url(user):
            cache.set(cache_key, True, timeout=_resend_cooldown_seconds())
            return True, _(
                "Resend test mode blocked the email. Use the development link on this page."
            )
        return False, str(exc)

    cache.set(cache_key, True, timeout=_resend_cooldown_seconds())
    return True, _("Verification email sent. Check your inbox.")


@transaction.atomic
def verify_email_with_token(token_value: str) -> EmailVerificationResult:
    token = (
        EmailVerificationToken.objects.select_for_update()
        .select_related("user")
        .filter(token=token_value)
        .first()
    )
    if token is None:
        return EmailVerificationResult(
            success=False,
            error_code="invalid",
            message=_("This verification link is invalid."),
        )

    if token.used_at is not None:
        return EmailVerificationResult(
            success=False,
            user=token.user,
            error_code="used",
            message=_("This verification link has already been used."),
        )

    if token.is_expired:
        return EmailVerificationResult(
            success=False,
            user=token.user,
            error_code="expired",
            message=_("This verification link has expired. Request a new one."),
        )

    user = token.user
    current_email = (user.email or "").strip().lower()
    if current_email != token.email:
        return EmailVerificationResult(
            success=False,
            user=user,
            error_code="email_changed",
            message=_(
                "Your email address changed after this link was sent. "
                "Request a new verification email."
            ),
        )

    now = timezone.now()
    token.used_at = now
    token.save(update_fields=["used_at"])

    user.email_verified_at = now
    user.save(update_fields=["email_verified_at", "updated_at"])

    return EmailVerificationResult(
        success=True,
        user=user,
        message=_("Your email address is confirmed."),
    )


def mark_email_unverified(user: User) -> None:
    user.email_verified_at = None
    user.save(update_fields=["email_verified_at", "updated_at"])
    _invalidate_active_tokens(user)
