"""Optional Sentry integration — active only when SENTRY_DSN is set."""

from django.conf import settings


def init_sentry():
    dsn = getattr(settings, "SENTRY_DSN", "") or ""
    if not dsn:
        return

    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=dsn,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        environment=getattr(settings, "SENTRY_ENVIRONMENT", "production"),
        traces_sample_rate=getattr(settings, "SENTRY_TRACES_SAMPLE_RATE", 0.1),
        send_default_pii=False,
    )
