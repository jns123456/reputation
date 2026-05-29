"""Helpers for HTMX-aware HTTP responses."""

from django.http import HttpResponse
from django.shortcuts import redirect


def absolute_url(request, url):
    if url.startswith(("http://", "https://")):
        return url
    return request.build_absolute_uri(url)


def redirect_response(request, url):
    """Redirect full-page navigations; use HX-Redirect for HTMX partial targets."""
    target = absolute_url(request, url)
    if request.headers.get("HX-Request"):
        response = HttpResponse(status=204)
        response["HX-Redirect"] = target
        return response
    return redirect(target)
