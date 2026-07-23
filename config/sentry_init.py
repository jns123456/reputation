"""Optional Sentry integration — active only when SENTRY_DSN is set."""

import re

from django.conf import settings


def init_sentry():
    dsn = getattr(settings, "SENTRY_DSN", "") or ""
    if not dsn:
        return

    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import ignore_logger

    sentry_sdk.init(
        dsn=dsn,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        environment=getattr(settings, "SENTRY_ENVIRONMENT", "production"),
        traces_sampler=_traces_sampler,
        before_send=_before_send,
        send_default_pii=False,
    )
    # LoggingIntegration (via CeleryIntegration) can emit before before_send in workers.
    ignore_logger("multiprocessing")


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
    "World Cup match sync failed for category",
    "Failed to fetch World Cup match event",
    "Failed to fetch H2H match event",
    "Failed to fetch Polymarket market",
    "Failed to fetch Polymarket event",
    "Failed to fetch Polymarket price history",
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
        "ChunkedEncodingError",
        "ProtocolError",
    }
    exc_info = hint.get("exc_info")
    if exc_info and exc_info[0] is not None:
        exc_name = getattr(exc_info[0], "__name__", "")
        if exc_name in transient_types:
            return True
        if exc_name == "HTTPError":
            exc = exc_info[1]
            response = getattr(exc, "response", None)
            if response is not None and (
                response.status_code >= 500 or response.status_code == 422
            ):
                return True

    for entry in event.get("exception", {}).get("values", []):
        entry_type = entry.get("type")
        if entry_type in transient_types:
            return True
        if entry_type == "HTTPError":
            value = entry.get("value") or ""
            if "422" in value and "Unprocessable Entity" in value:
                return True
            if "Server Error" in value and re.search(r"\b5\d{2}\b", value):
                return True
    return False


def _is_transient_polymarket_fetch_noise(event, hint) -> bool:
    """Drop handled Polymarket upstream failures from integrations fetch/sync paths."""
    logger_name = event.get("logger")
    if logger_name not in {
        "integrations.services",
        "integrations.sync",
        "integrations.polymarket.chart",
    }:
        return False

    message = _event_message(event)
    if not any(message.startswith(prefix) for prefix in _TRANSIENT_POLYMARKET_LOG_MESSAGES):
        return False

    return _is_transient_polymarket_upstream_exception(event, hint)


def _is_embedded_sync_transient_db_noise(event, hint) -> bool:
    """Drop transient PostgreSQL SSL drops from the embedded market sync thread."""
    if event.get("logger") != "integrations.market_sync_scheduler":
        return False

    message = _event_message(event)
    if "Embedded market sync loop" not in message:
        return False

    transient_types = {"OperationalError", "InterfaceError", "DatabaseError"}
    exc_info = hint.get("exc_info")
    if exc_info and exc_info[0] is not None:
        exc_name = getattr(exc_info[0], "__name__", "")
        if exc_name in transient_types:
            return True

    for entry in event.get("exception", {}).get("values", []):
        if entry.get("type") in transient_types:
            value = (entry.get("value") or "").lower()
            if any(token in value for token in ("ssl", "eof", "connection", "closed")):
                return True
    return False


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


def _is_celery_worker_sigterm_noise(message: str) -> bool:
    """Drop expected Celery fork-pool SIGTERM noise during Heroku dyno cycling."""
    if "ForkPoolWorker" not in message:
        return False
    lowered = message.lower()
    return (
        "sigterm" in lowered
        or "exitcode 15" in lowered
        or "signal 15" in lowered
    )


def _is_gunicorn_worker_sigterm_noise(event, message: str) -> bool:
    """Drop expected Gunicorn worker SIGTERM noise during Heroku dyno cycling."""
    if event.get("logger") != "gunicorn.error":
        return False
    return bool(re.search(r"Worker \(pid:\d+\) was sent SIGTERM", message, re.IGNORECASE))


def _is_transient_postgres_oom(event, hint) -> bool:
    """Drop handled PostgreSQL OOM during market import resolution."""
    if event.get("logger") != "integrations.services":
        return False

    message = _event_message(event)
    if "Deferred prediction resolution after import" not in message:
        return False

    oom_markers = ("out of memory", "failed on request of size")
    exc_info = hint.get("exc_info")
    if exc_info and exc_info[1] is not None:
        if any(marker in str(exc_info[1]).lower() for marker in oom_markers):
            return True

    for entry in event.get("exception", {}).get("values", []):
        if entry.get("type") not in {"OperationalError", "OutOfMemory"}:
            continue
        value = (entry.get("value") or "").lower()
        if any(marker in value for marker in oom_markers):
            return True
    return False


def _before_send(event, hint):
    """Drop expected worker SIGTERM noise during Heroku dyno cycling."""
    exc_info = hint.get("exc_info")
    if exc_info and exc_info[0] is not None:
        exc_name = getattr(exc_info[0], "__name__", "")
        if exc_name in {"WorkerLostError", "WorkerTerminate"}:
            return None

    if _is_handled_redis_cache_error(event, hint):
        return None

    message = _event_message(event)
    if _is_celery_worker_sigterm_noise(message):
        return None

    if _is_gunicorn_worker_sigterm_noise(event, message):
        return None

    if _is_best_effort_enqueue_noise(event, hint):
        return None

    if _is_transient_polymarket_fetch_noise(event, hint):
        return None

    if _is_embedded_sync_transient_db_noise(event, hint):
        return None

    if _is_transient_postgres_oom(event, hint):
        return None

    return event


def _traces_sampler(sampling_context):
    """Skip high-noise internal endpoints from performance traces."""
    transaction_context = sampling_context.get("transaction_context") or {}
    name = transaction_context.get("name") or ""
    if "/api/v1/schema" in name:
        return 0.0
    return getattr(settings, "SENTRY_TRACES_SAMPLE_RATE", 0.1)
