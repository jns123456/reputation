"""Landing hero MP4 — byte-range aware for iOS Safari."""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse

LANDING_VIDEO_RELATIVE = Path("videos") / "landing-hero.mp4"
CONTENT_TYPE = "video/mp4"
_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


def landing_video_path() -> Path:
    return Path(settings.BASE_DIR) / "static" / LANDING_VIDEO_RELATIVE


def serve_landing_hero_video(request) -> HttpResponse | FileResponse:
    """Serve the landing MP4 with Accept-Ranges (required by iOS Safari)."""
    path = landing_video_path()
    if not path.is_file():
        raise Http404

    file_size = path.stat().st_size
    range_header = request.META.get("HTTP_RANGE", "").strip()

    if range_header:
        match = _RANGE_RE.match(range_header)
        if not match:
            return HttpResponse(status=416)

        start_str, end_str = match.groups()
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else file_size - 1

        if start >= file_size or start > end:
            return HttpResponse(status=416)

        end = min(end, file_size - 1)
        length = end - start + 1

        with path.open("rb") as fh:
            fh.seek(start)
            chunk = fh.read(length)

        response = HttpResponse(chunk, status=206, content_type=CONTENT_TYPE)
        response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        response["Content-Length"] = str(length)
    else:
        response = FileResponse(path.open("rb"), content_type=CONTENT_TYPE)
        response["Content-Length"] = str(file_size)

    response["Accept-Ranges"] = "bytes"
    response["Cache-Control"] = "public, max-age=86400"
    return response
