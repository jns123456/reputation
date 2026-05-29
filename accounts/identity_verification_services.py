"""Platform identity verification (verified badge) review."""

from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _lazy

User = get_user_model()


class IdentityVerificationError(Exception):
    """Raised when a verification action is invalid for the user's state."""


def get_pending_verification_users():
    return User.objects.filter(
        verification_requested=True,
        is_verified=False,
    ).order_by("date_joined")


def approve_identity_verification(user: User) -> None:
    if not user.verification_requested or user.is_verified:
        raise IdentityVerificationError(
            _lazy("This user does not have a pending verification request.")
        )
    user.is_verified = True
    user.save(update_fields=["is_verified", "updated_at"])


def reject_identity_verification(user: User) -> None:
    if not user.verification_requested or user.is_verified:
        raise IdentityVerificationError(
            _lazy("This user does not have a pending verification request.")
        )
    user.verification_requested = False
    user.save(update_fields=["verification_requested", "updated_at"])
