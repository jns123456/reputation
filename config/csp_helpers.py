"""Content-Security-Policy helpers."""

from urllib.parse import urlparse


def sentry_csp_report_uri(dsn: str) -> str:
    """Build Sentry security endpoint for CSP violation reports."""
    dsn = (dsn or "").strip()
    if not dsn:
        return ""

    parsed = urlparse(dsn)
    public_key = parsed.username or ""
    project_id = (parsed.path or "").strip("/")
    host = parsed.hostname or ""
    if not public_key or not project_id or not host:
        return ""

    return f"https://{host}/api/{project_id}/security/?sentry_key={public_key}"
