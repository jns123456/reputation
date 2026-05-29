from django.shortcuts import redirect
from django.urls import reverse

from accounts.email_verification_services import user_requires_email_verification


class EmailVerificationRequiredMiddleware:
    """Block unverified users until they confirm their email address."""

    EXEMPT_PREFIXES = (
        "/accounts/verify-email/",
        "/accounts/logout/",
        "/accounts/login/",
        "/accounts/signup/",
        "/accounts/auth0/",
        "/accounts/push/",
        "/admin/",
        "/static/",
        "/media/",
        "/i18n/",
        "/sw.js",
        "/manifest.webmanifest",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and user_requires_email_verification(request.user):
            path = request.path
            if not any(path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES):
                return redirect("accounts:verify_email_pending")
        return self.get_response(request)


class ProfileSetupRequiredMiddleware:
    """Redirect new users to identity setup until onboarding is complete."""

    EXEMPT_PREFIXES = (
        "/accounts/setup/",
        "/accounts/verify-email/",
        "/accounts/logout/",
        "/accounts/login/",
        "/accounts/signup/",
        "/accounts/auth0/",
        "/accounts/push/",
        "/admin/",
        "/static/",
        "/i18n/",
        "/sw.js",
        "/manifest.webmanifest",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.onboarding_completed:
            path = request.path
            if not any(path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES):
                return redirect("accounts:profile_setup")
        return self.get_response(request)
