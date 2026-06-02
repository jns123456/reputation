"""Production deploy validation — fail fast on insecure defaults."""

from django.core.exceptions import ImproperlyConfigured

INSECURE_SECRET_KEY = "django-insecure-dev-key-change-in-production"
MIN_SECRET_KEY_LENGTH = 50


def validate_production_settings(
    *,
    debug: bool,
    secret_key: str,
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

    if errors:
        raise ImproperlyConfigured(" ".join(errors))
