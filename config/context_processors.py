from django.conf import settings


def static_version(request):
    """Append ?v=mtime to static URLs in dev so CSS/JS edits aren't stuck in browser cache."""
    if not settings.DEBUG:
        return {"static_version": None}
    css_path = settings.BASE_DIR / "static" / "css" / "proofrep-ui.css"
    try:
        return {"static_version": int(css_path.stat().st_mtime)}
    except OSError:
        return {"static_version": None}
