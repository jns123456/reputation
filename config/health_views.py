"""Lightweight health checks for load balancers and deploy probes."""

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


def _check_database():
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return "ok"


def _check_cache():
    if not getattr(settings, "USE_REDIS_CACHE", False):
        return "skipped"
    from django.core.cache import cache

    probe_key = "health:probe"
    cache.set(probe_key, "1", timeout=5)
    if cache.get(probe_key) != "1":
        raise RuntimeError("cache read/write mismatch")
    cache.delete(probe_key)
    return "ok"


@require_GET
def health(request):
    """Return 200 when core dependencies respond; 503 otherwise."""
    checks = {}
    status_code = 200
    try:
        checks["database"] = _check_database()
    except Exception as exc:
        checks["database"] = f"error: {exc.__class__.__name__}"
        status_code = 503
    try:
        checks["cache"] = _check_cache()
    except Exception as exc:
        checks["cache"] = f"error: {exc.__class__.__name__}"
        status_code = 503
    payload = {"status": "ok" if status_code == 200 else "degraded", "checks": checks}
    return JsonResponse(payload, status=status_code)
