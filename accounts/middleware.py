from django.shortcuts import redirect
from django.urls import reverse


class ProfileSetupRequiredMiddleware:
    """Redirect new users to identity setup until onboarding is complete."""

    EXEMPT_PREFIXES = (
        "/accounts/setup/",
        "/accounts/logout/",
        "/accounts/login/",
        "/accounts/signup/",
        "/admin/",
        "/static/",
        "/i18n/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.onboarding_completed:
            path = request.path
            if not any(path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES):
                return redirect("accounts:profile_setup")
        return self.get_response(request)
