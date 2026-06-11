"""Authentication, signup, and email verification views."""

from urllib.parse import urlencode

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.urls import reverse_lazy
from django.contrib import messages
from django.conf import settings
from django.utils.translation import gettext as _
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from accounts import abuse_services
from accounts.email_verification_services import (
    get_active_verification_url,
    resend_verification_email,
    send_verification_email,
    user_requires_email_verification,
    verify_email_with_token,
)
from accounts.email_services import EmailDeliveryError
from accounts.forms import SignUpForm, StyledPasswordResetForm, StyledSetPasswordForm
from accounts.http_utils import enforce_ip_rate_limit
from accounts.models import User
from accounts.notification_services import queue_login_notification_toast


class CustomLoginView(LoginView):
    template_name = "accounts/login.html"

    def post(self, request, *args, **kwargs):
        try:
            enforce_ip_rate_limit(request=request, action="login")
        except abuse_services.RateLimitExceeded:
            messages.error(
                request,
                _("Too many login attempts. Please wait a few minutes and try again."),
            )
            return self.render_to_response(self.get_context_data())
        return super().post(request, *args, **kwargs)

    def get_success_url(self):
        if user_requires_email_verification(self.request.user):
            return reverse("accounts:verify_email_pending")
        if not self.request.user.onboarding_completed:
            return reverse("accounts:profile_setup")
        return reverse("accounts:profile", kwargs={"username": self.request.user.username})

    def form_valid(self, form):
        response = super().form_valid(form)
        queue_login_notification_toast(request=self.request)
        return response


class CustomLogoutView(LogoutView):
    next_page = "dashboard:landing"

    def dispatch(self, request, *args, **kwargs):
        # Capture the Auth0 session marker before logout clears the session, so
        # we can also end the Auth0 (Universal Login) session — otherwise the user
        # stays silently signed in at Auth0 and "logout" would log them right back in.
        auth0_session = bool(request.session.get("auth0_id_token")) and settings.AUTH0_ENABLED
        response = super().dispatch(request, *args, **kwargs)
        if auth0_session:
            return_to = request.build_absolute_uri(reverse("dashboard:landing"))
            params = urlencode(
                {"returnTo": return_to, "client_id": settings.AUTH0_CLIENT_ID}
            )
            return redirect(f"https://{settings.AUTH0_DOMAIN}/v2/logout?{params}")
        return response


class CustomPasswordResetView(PasswordResetView):
    """Rate-limited password reset request; email delivery via our email layer."""

    template_name = "accounts/password_reset_form.html"
    form_class = StyledPasswordResetForm
    success_url = reverse_lazy("accounts:password_reset_done")

    def post(self, request, *args, **kwargs):
        try:
            enforce_ip_rate_limit(request=request, action="password_reset")
        except abuse_services.RateLimitExceeded:
            messages.error(
                request,
                _("Too many reset requests. Please wait a while and try again."),
            )
            return self.render_to_response(self.get_context_data())
        return super().post(request, *args, **kwargs)


class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    form_class = StyledSetPasswordForm
    success_url = reverse_lazy("accounts:password_reset_complete")


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"


def _post_auth_redirect(user):
    """Where to send a freshly authenticated user (shared by login flows)."""
    if not user.onboarding_completed:
        return redirect("accounts:profile_setup")
    return redirect("accounts:profile", username=user.username)


def auth0_login(request):
    """Kick off the Auth0 Universal Login redirect."""
    from accounts.auth0 import get_auth0_client

    client = get_auth0_client()
    if client is None:
        messages.error(request, _("Auth0 sign-in is not available right now."))
        return redirect("accounts:login")
    redirect_uri = request.build_absolute_uri(reverse("accounts:auth0_callback"))
    authorize_kwargs = {}
    connection = (request.GET.get("connection") or "").strip()
    # Allowlist: only connections we intentionally expose may be requested,
    # so attackers can't probe arbitrary Auth0 IdP connections.
    if connection and connection == settings.AUTH0_GOOGLE_CONNECTION:
        authorize_kwargs["connection"] = connection
    return client.authorize_redirect(request, redirect_uri, **authorize_kwargs)


def auth0_callback(request):
    """Handle the Auth0 redirect: exchange the code, map the user, log in."""
    from accounts.auth0 import Auth0LinkDenied, get_auth0_client, get_or_create_user_from_auth0

    client = get_auth0_client()
    if client is None:
        return redirect("accounts:login")

    try:
        enforce_ip_rate_limit(request=request, action="login")
    except abuse_services.RateLimitExceeded:
        messages.error(
            request,
            _("Too many login attempts. Please wait a few minutes and try again."),
        )
        return redirect("accounts:login")

    try:
        token = client.authorize_access_token(request)
    except Exception:
        messages.error(
            request,
            _("We couldn't complete the Auth0 sign-in. Please try again."),
        )
        return redirect("accounts:login")

    userinfo = token.get("userinfo")
    if not userinfo:
        try:
            userinfo = client.userinfo(token=token)
        except Exception:
            userinfo = {}
    if not userinfo or not userinfo.get("sub"):
        messages.error(request, _("Auth0 did not return a valid profile."))
        return redirect("accounts:login")

    try:
        user = get_or_create_user_from_auth0(userinfo)
    except Auth0LinkDenied:
        messages.error(
            request,
            _(
                "We couldn't sign you in: your identity provider has not verified "
                "this email address. Verify it there, or sign in with your password."
            ),
        )
        return redirect("accounts:login")
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session["auth0_id_token"] = token.get("id_token", "")
    queue_login_notification_toast(request=request)
    return _post_auth_redirect(user)


def signup(request):
    if request.user.is_authenticated:
        if user_requires_email_verification(request.user):
            return redirect("accounts:verify_email_pending")
        if not request.user.onboarding_completed:
            return redirect("accounts:profile_setup")
        return redirect("accounts:profile", username=request.user.username)
    if request.method == "POST":
        try:
            enforce_ip_rate_limit(request=request, action="registration")
        except abuse_services.RateLimitExceeded:
            messages.error(
                request,
                _(
                    "Too many sign-up attempts from this connection. "
                    "Please try again later."
                ),
            )
            form = SignUpForm(request.POST)
            return render(request, "accounts/signup.html", _signup_context(request, form))
        form = SignUpForm(request.POST)
        human_check = _run_signup_human_verification(request)
        if not human_check["allowed"]:
            messages.error(
                request,
                _("We could not verify you are human. Please try again."),
            )
            return render(request, "accounts/signup.html", _signup_context(request, form))
        if form.is_valid():
            user = form.save()
            if human_check["passed"] and human_check["provider"] != "noop":
                user.verification_status = User.VerificationStatus.HUMAN_CHALLENGE_PASSED
                user.save(update_fields=["verification_status", "updated_at"])
            login(request, user)
            try:
                send_verification_email(user)
            except EmailDeliveryError as exc:
                if getattr(settings, "EMAIL_VERIFICATION_DEV_SHOW_LINK", settings.DEBUG):
                    messages.warning(
                        request,
                        _(
                            "We could not email the verification link (Resend test mode). "
                            "Use the development link on the next page."
                        ),
                    )
                else:
                    messages.error(request, str(exc))
            except Exception:
                messages.error(
                    request,
                    _(
                        "Your account was created, but we could not send the verification email. "
                        "Try resending from the next screen."
                    ),
                )
            messages.info(
                request,
                _("Check your inbox and confirm your email to continue."),
            )
            return redirect("accounts:verify_email_pending")
    else:
        form = SignUpForm()
    return render(request, "accounts/signup.html", _signup_context(request, form))


def _signup_context(request, form):
    return {
        "form": form,
        "turnstile_site_key": getattr(settings, "TURNSTILE_SITE_KEY", ""),
    }


def _run_signup_human_verification(request):
    """Run the anti-bot provider for a signup POST (AGENTS.md §16).

    Returns {allowed, passed, provider}. When verification is not required, a
    failed/absent challenge still allows signup (it only raises the risk score);
    when required, a failed challenge blocks account creation.
    """
    from accounts.human_verification import verify_human_signal
    from accounts.models import AbuseEvent
    from accounts.risk_services import calculate_request_risk_score

    token = request.POST.get("cf-turnstile-response", "") or request.POST.get(
        "human_verification_token", ""
    )
    result = verify_human_signal(token=token, request=request)
    required = getattr(settings, "HUMAN_VERIFICATION_REQUIRED", False)
    allowed = result.passed or not required

    if not result.passed:
        risk = calculate_request_risk_score(
            ip=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            is_human_verified=False,
        )
        from accounts.abuse_services import record_abuse_event

        record_abuse_event(
            event_type=AbuseEvent.EventType.REGISTRATION_RISK,
            severity=AbuseEvent.Severity.MEDIUM if required else AbuseEvent.Severity.LOW,
            scope="registration",
            risk_score=risk,
            action_taken="blocked" if not allowed else "flagged",
            reason=f"Human verification failed (provider={result.provider}).",
        )
    return {"allowed": allowed, "passed": result.passed, "provider": result.provider}


@login_required
def verify_email_pending(request):
    if not user_requires_email_verification(request.user):
        if not request.user.onboarding_completed:
            return redirect("accounts:profile_setup")
        return redirect("accounts:profile", username=request.user.username)
    dev_verification_url = None
    if getattr(settings, "EMAIL_VERIFICATION_DEV_SHOW_LINK", settings.DEBUG):
        dev_verification_url = get_active_verification_url(request.user)
    return render(
        request,
        "accounts/verify_email_pending.html",
        {
            "profile_user": request.user,
            "dev_verification_url": dev_verification_url,
        },
    )


@login_required
@require_POST
def verify_email_resend(request):
    sent, message = resend_verification_email(request.user)
    if sent:
        messages.success(request, message)
    else:
        messages.warning(request, message)
    return redirect("accounts:verify_email_pending")


def verify_email_confirm(request, token):
    result = verify_email_with_token(token)
    if result.success and result.user is not None:
        if request.user.is_authenticated:
            if request.user.pk != result.user.pk:
                messages.warning(
                    request,
                    _(
                        "Email confirmed for another account. "
                        "Log in with that account to continue."
                    ),
                )
            else:
                messages.success(request, result.message)
                if not result.user.onboarding_completed:
                    return redirect("accounts:profile_setup")
                return redirect("accounts:profile", username=result.user.username)
        else:
            login(request, result.user)
            messages.success(request, result.message)
            if not result.user.onboarding_completed:
                return redirect("accounts:profile_setup")
            return redirect("accounts:profile", username=result.user.username)

    status = "error"
    if result.error_code == "expired":
        status = "expired"
    elif result.error_code == "used":
        status = "used"

    return render(
        request,
        "accounts/verify_email_result.html",
        {
            "result": result,
            "status": status,
        },
    )
