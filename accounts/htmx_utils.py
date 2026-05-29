"""Helpers for HTMX-aware HTTP responses."""

from django.http import HttpResponse
from django.shortcuts import redirect


def redirect_response(request, url):
    """Redirect full-page navigations; use HX-Redirect for HTMX partial targets."""
    if request.headers.get("HX-Request"):
        response = HttpResponse(status=204)
        response["HX-Redirect"] = url
        return response
    return redirect(url)
