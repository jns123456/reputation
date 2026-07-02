from django.conf import settings
from django.urls import reverse
from django.utils import translation

from accounts.client_timezone import get_client_timezone_name, timezone_display_label
from accounts.country_language import language_for_request_country
from accounts.email_verification_services import user_requires_email_verification
from accounts.htmx_utils import redirect_response


class ClientTimezoneMiddleware:
    """Resolve visitor timezone for sports kickoff display only (see ``local_kickoff_time``)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tz_name = get_client_timezone_name(request)
        request.client_timezone_name = tz_name
        request.client_timezone_label = timezone_display_label(tz_name)
        return self.get_response(request)


class CountryLanguageMiddleware:
    """
    When the user has not chosen a language (no django_language cookie), infer
    locale from country (IP / CDN headers) and set the official language cookie.
    Runs after LocaleMiddleware so country wins over Accept-Language.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        auto_language = None
        if not request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME):
            auto_language = language_for_request_country(request)
            if auto_language:
                translation.activate(auto_language)
                request.LANGUAGE_CODE = auto_language

        response = self.get_response(request)

        if auto_language and not request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME):
            response.set_cookie(
                settings.LANGUAGE_COOKIE_NAME,
                auto_language,
                max_age=settings.LANGUAGE_COOKIE_AGE,
                path=settings.LANGUAGE_COOKIE_PATH,
                domain=settings.LANGUAGE_COOKIE_DOMAIN,
                secure=settings.LANGUAGE_COOKIE_SECURE,
                httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
                samesite=settings.LANGUAGE_COOKIE_SAMESITE,
            )
        return response


class EmailVerificationRequiredMiddleware:
    """Block unverified users until they confirm their email address."""

    EXEMPT_PREFIXES = (
        "/accounts/notifications/",
        "/accounts/verify-email/",
        "/accounts/logout/",
        "/accounts/login/",
        "/accounts/signup/",
        "/accounts/auth0/",
        "/accounts/delete/",
        "/accounts/push/",
        "/accounts/password-reset/",
        "/health/",
        "/static/",
        "/media/",
        "/assets/",
        "/i18n/",
        "/p/",
        "/c/",
        "/@",
        "/sw.js",
        "/manifest.webmanifest",
    )

    def __init__(self, get_response):
        self.get_response = get_response
        # Admin mount point is configurable (ADMIN_URL_PATH); exempt it dynamically.
        self.exempt_prefixes = self.EXEMPT_PREFIXES + ("/" + settings.ADMIN_URL_PATH,)

    def __call__(self, request):
        if request.user.is_authenticated and user_requires_email_verification(request.user):
            path = request.path
            if not any(path.startswith(prefix) for prefix in self.exempt_prefixes):
                return redirect_response(
                    request,
                    reverse("accounts:verify_email_pending"),
                )
        return self.get_response(request)



class ProfileSetupRequiredMiddleware:
    """Redirect new users to identity setup until onboarding is complete."""

    EXEMPT_PREFIXES = (
        "/accounts/setup/",
        "/accounts/notifications/",
        "/accounts/verify-email/",
        "/accounts/logout/",
        "/accounts/login/",
        "/accounts/signup/",
        "/accounts/auth0/",
        "/accounts/delete/",
        "/accounts/push/",
        "/accounts/password-reset/",
        "/health/",
        "/static/",
        "/assets/",
        "/i18n/",
        "/p/",
        "/c/",
        "/@",
        "/sw.js",
        "/manifest.webmanifest",
    )

    def __init__(self, get_response):
        self.get_response = get_response
        # Admin mount point is configurable (ADMIN_URL_PATH); exempt it dynamically.
        self.exempt_prefixes = self.EXEMPT_PREFIXES + ("/" + settings.ADMIN_URL_PATH,)

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.onboarding_completed:
            path = request.path
            if not any(path.startswith(prefix) for prefix in self.exempt_prefixes):
                return redirect_response(
                    request,
                    reverse("accounts:profile_setup"),
                )
        return self.get_response(request)
