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


def platform_context(request):
    from reputation.weekly_contest_services import contest_program_has_ended

    return {
        "base_app_id": getattr(settings, "BASE_APP_ID", "") or "",
        "weekly_contest_enabled": getattr(settings, "WEEKLY_CONTEST_ENABLED", True),
        "weekly_contest_prize_usd": getattr(settings, "WEEKLY_CONTEST_PRIZE_USD", 5),
        "weekly_contest_program_ended": contest_program_has_ended(),
        "contest_payouts_enabled": getattr(settings, "CONTEST_PAYOUTS_ENABLED", True),
    }
