"""Production deploy validation — fail fast on insecure defaults."""

from django.core.exceptions import ImproperlyConfigured

INSECURE_SECRET_KEY = "django-insecure-dev-key-change-in-production"
INSECURE_EAS_OFFCHAIN_SIGNING_KEY = "change-me-for-production-attestations"
MIN_SECRET_KEY_LENGTH = 50


def validate_production_settings(
    *,
    debug: bool,
    secret_key: str,
    eas_offchain_signing_key: str,
    email_verification_dev_show_link: bool,
    running_tests: bool = False,
) -> None:
    """Raise ``ImproperlyConfigured`` when production settings are unsafe."""
    if debug or running_tests:
        return

    errors: list[str] = []

    if not secret_key or secret_key == INSECURE_SECRET_KEY:
        errors.append(
            "SECRET_KEY must be set to a unique random value in production "
            "(never use the django-insecure default)."
        )
    elif len(secret_key) < MIN_SECRET_KEY_LENGTH:
        errors.append(
            f"SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} characters in production."
        )

    if email_verification_dev_show_link:
        errors.append(
            "EMAIL_VERIFICATION_DEV_SHOW_LINK must be False in production."
        )

    if (
        not eas_offchain_signing_key
        or eas_offchain_signing_key == secret_key
        or eas_offchain_signing_key == INSECURE_EAS_OFFCHAIN_SIGNING_KEY
    ):
        errors.append(
            "EAS_OFFCHAIN_SIGNING_KEY must be set to a dedicated random value in production "
            "(never reuse SECRET_KEY or the change-me placeholder)."
        )
    elif len(eas_offchain_signing_key) < MIN_SECRET_KEY_LENGTH:
        errors.append(
            f"EAS_OFFCHAIN_SIGNING_KEY must be at least {MIN_SECRET_KEY_LENGTH} characters in production."
        )

    if errors:
        raise ImproperlyConfigured(" ".join(errors))
