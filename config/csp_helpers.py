"""Content-Security-Policy helpers."""

import re
from urllib.parse import urlparse

# Cloudflare Turnstile renders challenge UI in an iframe on this host.
TURNSTILE_FRAME_HOST = "challenges.cloudflare.com"
# Turnstile and other third-party widgets load webfonts from Google Fonts CDN.
GOOGLE_FONTS_STATIC_HOST = "fonts.gstatic.com"
# Iconify fetches MDI (and related) icon JSON from the unisvg API.
ICONIFY_UNISVG_CONNECT_HOST = "https://api.unisvg.com"


def ensure_frame_src_host(policy: str, host: str) -> str:
    """Add *host* to frame-src when missing (idempotent)."""
    policy = policy or ""
    host = (host or "").strip()
    if not policy or not host:
        return policy

    match = re.search(r"frame-src\s+([^;]+)", policy)
    if not match:
        return policy
    if host in match.group(1).split():
        return policy

    start, end = match.span(1)
    return f"{policy[:end]} {host}{policy[end:]}"


def ensure_turnstile_frame_src(policy: str) -> str:
    """Allow Cloudflare Turnstile challenge iframes in frame-src."""
    return ensure_frame_src_host(policy, TURNSTILE_FRAME_HOST)


def ensure_font_src_host(policy: str, host: str) -> str:
    """Add *host* to font-src when missing (idempotent)."""
    policy = policy or ""
    host = (host or "").strip()
    if not policy or not host:
        return policy

    match = re.search(r"font-src\s+([^;]+)", policy)
    if not match:
        return policy
    if host in match.group(1).split():
        return policy

    start, end = match.span(1)
    return f"{policy[:end]} {host}{policy[end:]}"


def ensure_google_fonts_font_src(policy: str) -> str:
    """Allow Google Fonts static files used by third-party widgets."""
    return ensure_font_src_host(policy, GOOGLE_FONTS_STATIC_HOST)


def ensure_connect_src_host(policy: str, host: str) -> str:
    """Add *host* to connect-src when missing (idempotent)."""
    policy = policy or ""
    host = (host or "").strip()
    if not policy or not host:
        return policy

    match = re.search(r"connect-src\s+([^;]+)", policy)
    if not match:
        return policy
    sources = match.group(1).split()
    if host in sources:
        return policy
    bare = host.removeprefix("https://").removeprefix("http://")
    if bare in sources or f"https://{bare}" in sources:
        return policy

    start, end = match.span(1)
    return f"{policy[:end]} {host}{policy[end:]}"


def ensure_iconify_connect_src(policy: str) -> str:
    """Allow Iconify runtime fetches for MDI and related icon sets."""
    return ensure_connect_src_host(policy, ICONIFY_UNISVG_CONNECT_HOST)


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
