"""HTTP helpers shared across account and content views."""

from django.conf import settings
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme

from accounts.country_language import get_client_ip


def client_ip_identifier(request) -> str:
    """Cache key fragment for IP-keyed rate limits."""
    return f"ip:{get_client_ip(request) or 'unknown'}"


def safe_redirect_to_referer(request, fallback="/"):
    """Redirect to Referer only when it targets this site (open-redirect safe)."""
    referer = (request.META.get("HTTP_REFERER") or "").strip()
    if referer and url_has_allowed_host_and_scheme(
        referer,
        allowed_hosts={request.get_host(), *settings.ALLOWED_HOSTS},
        require_https=request.is_secure(),
    ):
        return redirect(referer)
    return redirect(fallback)


def enforce_ip_rate_limit(*, request, action):
    """Apply IP-keyed rate limits (login, registration). Raises RateLimitExceeded."""
    from accounts import abuse_services

    abuse_services.enforce_rate_limit(
        action=action,
        identifier=client_ip_identifier(request),
        tier="ip",
    )
