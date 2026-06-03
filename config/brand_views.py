"""Public brand assets at stable URLs (Auth0 Universal Login logo, etc.)."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

AUTH0_LOGO_RELATIVE = Path("images") / "predictstamp-auth0-logo.jpg"
CONTENT_TYPE = "image/jpeg"


def auth0_logo_path() -> Path:
    return Path(settings.BASE_DIR) / "static" / AUTH0_LOGO_RELATIVE


@require_GET
@cache_control(public=True, max_age=86400)
def serve_auth0_logo(request) -> FileResponse:
    """Stable HTTPS URL for Auth0 Branding → Universal Login logo."""
    path = auth0_logo_path()
    if not path.is_file():
        raise Http404
    return FileResponse(path.open("rb"), content_type=CONTENT_TYPE)
