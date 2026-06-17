"""Optional Content-Security-Policy (report-only by default)."""

from django.conf import settings

from config.csp_helpers import (
    ensure_google_fonts_font_src,
    ensure_iconify_connect_src,
    ensure_turnstile_frame_src,
    sanitize_malformed_connect_src,
)


class ContentSecurityPolicyMiddleware:
    """Attach a CSP header when ``CSP_ENABLED`` is true."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not getattr(settings, "CSP_ENABLED", False):
            return response
        policy = sanitize_malformed_connect_src(
            ensure_iconify_connect_src(
                ensure_google_fonts_font_src(
                    ensure_turnstile_frame_src(
                        getattr(settings, "CONTENT_SECURITY_POLICY", "")
                    )
                )
            )
        )
        if not policy:
            return response
        header = (
            "Content-Security-Policy-Report-Only"
            if getattr(settings, "CSP_REPORT_ONLY", True)
            else "Content-Security-Policy"
        )
        response[header] = policy
        return response
