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
        traces_sampler=_traces_sampler,
        before_send=_before_send,
        send_default_pii=False,
    )


def _event_message(event):
    logentry = event.get("logentry")
    if isinstance(logentry, dict):
        message = logentry.get("message") or logentry.get("formatted")
        if message:
            return message
    message = event.get("message") or ""
    if isinstance(message, dict):
        return message.get("formatted") or ""
    return message


def _frames_include_module(event, module_name: str) -> bool:
    for entry in event.get("exception", {}).get("values", []):
        for frame in entry.get("stacktrace", {}).get("frames", []):
            if frame.get("module") == module_name:
                return True
    return False


def _stack_includes_filename(event, filename_suffix: str) -> bool:
    for entry in event.get("exception", {}).get("values", []):
        for frame in entry.get("stacktrace", {}).get("frames", []):
            filename = frame.get("filename") or frame.get("abs_path") or ""
            if filename.endswith(filename_suffix):
                return True
    return False


def _is_best_effort_enqueue_noise(event, hint) -> bool:
    message = _event_message(event)
    if "Failed to enqueue category sync" in message or "Failed to enqueue market refresh" in message:
        return True
    if event.get("logger") != "integrations.celery_utils":
        return False
    if "Failed to enqueue" in message:
        return True
    if not _frames_include_module(event, "integrations.celery_utils"):
        return False
    exc_info = hint.get("exc_info")
    if exc_info and exc_info[0] is not None:
        exc_name = getattr(exc_info[0], "__name__", "")
        if exc_name in {"ConnectionError", "OperationalError", "SSLError", "SSLEOFError"}:
            return True
    for entry in event.get("exception", {}).get("values", []):
        if entry.get("type") in {"ConnectionError", "OperationalError", "SSLError", "SSLEOFError"}:
            return True
    return False


_TRANSIENT_POLYMARKET_LOG_MESSAGES = (
    "Failed to fetch World Cup match event",
    "Failed to fetch H2H match event",
    "Failed to fetch Polymarket market",
    "Failed to fetch Polymarket event",
    "H2H/F1 sports sync failed for category",
    "Polymarket category sync failed for",
    "Polymarket top-volume sync failed",
)


def _is_transient_polymarket_upstream_exception(event, hint) -> bool:
    transient_types = {
        "ReadTimeout",
        "Timeout",
        "ConnectionError",
        "ConnectTimeout",
        "ReadTimeoutError",
    }
    exc_info = hint.get("exc_info")
    if exc_info and exc_info[0] is not None:
        exc_name = getattr(exc_info[0], "__name__", "")
        if exc_name in transient_types:
            return True
        if exc_name == "HTTPError":
            exc = exc_info[1]
            response = getattr(exc, "response", None)
            if response is not None and response.status_code >= 500:
                return True

    for entry in event.get("exception", {}).get("values", []):
        entry_type = entry.get("type")
        if entry_type in transient_types:
            return True
        if entry_type == "HTTPError":
            value = entry.get("value") or ""
            if "Server Error" in value and any(
                token in value for token in (" 500 ", " 502 ", " 503 ", " 504 ")
            ):
                return True
    return False


def _is_transient_polymarket_fetch_noise(event, hint) -> bool:
    """Drop handled Polymarket upstream failures from integrations fetch/sync paths."""
    logger_name = event.get("logger")
    if logger_name not in {"integrations.services", "integrations.sync"}:
        return False

    message = _event_message(event)
    if not any(message.startswith(prefix) for prefix in _TRANSIENT_POLYMARKET_LOG_MESSAGES):
        return False

    return _is_transient_polymarket_upstream_exception(event, hint)

def _is_handled_redis_cache_error(event, hint) -> bool:
    """Drop Redis cache failures already swallowed by ResilientRedisCache."""
    exc_info = hint.get("exc_info")
    if not exc_info or exc_info[0] is None:
        return False

    exc_name = getattr(exc_info[0], "__name__", "")
    exc_module = getattr(exc_info[0], "__module__", "")
    if exc_module != "redis.exceptions":
        return False
    if exc_name not in {"ConnectionError", "OutOfMemoryError", "TimeoutError"}:
        return False

    return _stack_includes_filename(event, "cache_backends.py")


def _before_send(event, hint):
    """Drop expected Celery worker SIGTERM noise during Heroku dyno cycling."""
    exc_info = hint.get("exc_info")
    if exc_info and exc_info[0] is not None:
        exc_name = getattr(exc_info[0], "__name__", "")
        if exc_name in {"WorkerLostError", "WorkerTerminate"}:
            return None

    if _is_handled_redis_cache_error(event, hint):
        return None

    message = _event_message(event)
    if "ForkPoolWorker" in message and "SIGTERM" in message:
        return None

    if _is_best_effort_enqueue_noise(event, hint):
        return None

    if _is_transient_polymarket_fetch_noise(event, hint):
        return None

    return event


def _traces_sampler(sampling_context):
    """Skip high-noise internal endpoints from performance traces."""
    transaction_context = sampling_context.get("transaction_context") or {}
    name = transaction_context.get("name") or ""
    if "/api/v1/schema" in name:
        return 0.0
    return getattr(settings, "SENTRY_TRACES_SAMPLE_RATE", 0.1)
