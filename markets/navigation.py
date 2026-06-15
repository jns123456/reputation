"""Market page navigation helpers."""

from django.urls import reverse

from accounts.http_utils import resolve_safe_return_url

MARKET_RETURN_SESSION_PREFIX = "market_return:"


def market_return_session_key(slug: str) -> str:
    return f"{MARKET_RETURN_SESSION_PREFIX}{slug}"


def resolve_market_return_url(request, *, slug: str) -> str:
    """Remember where the user came from before opening a market detail page."""
    market_path = reverse("markets:detail", kwargs={"slug": slug})
    create_path = reverse("predictions:create", kwargs={"slug": slug})

    return_url = resolve_safe_return_url(
        request,
        exclude_paths=(market_path, create_path),
    )
    session_key = market_return_session_key(slug)
    if return_url:
        request.session[session_key] = return_url
    else:
        return_url = request.session.get(session_key, "")
    return return_url
