from urllib.parse import urlencode

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib import messages
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from accounts.bookmark_selectors import is_bookmarked
from accounts.bookmark_services import toggle_bookmark
from accounts.bookmarks_services import build_bookmarks_page_items
from accounts.email_verification_services import (
    get_active_verification_url,
    mark_email_unverified,
    resend_verification_email,
    send_verification_email,
    user_requires_email_verification,
    verify_email_with_token,
)
from accounts.email_services import EmailDeliveryError
from accounts.follow_selectors import (
    get_follower_count,
    get_following_count,
    get_following_ids,
    is_following,
)
from accounts.follow_services import toggle_follow
from accounts.forms import NotificationPreferenceForm, ProfileEditForm, ProfileSetupForm, SignUpForm
from accounts.models import Bookmark, User
from accounts.category_selectors import get_user_category_breakdown
from accounts.notification_selectors import get_recent_notifications, get_user_notifications
from accounts.notification_services import (
    get_or_create_notification_preferences,
    mark_all_notifications_read,
    mark_notification_read,
    queue_login_notification_toast,
)
from accounts.selectors import get_user_prediction_history, search_user_matches
from accounts.user_search_selectors import is_valid_user_search_query


class CustomLoginView(LoginView):
    template_name = "accounts/login.html"

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
    return client.authorize_redirect(request, redirect_uri)


def auth0_callback(request):
    """Handle the Auth0 redirect: exchange the code, map the user, log in."""
    from accounts.auth0 import get_auth0_client, get_or_create_user_from_auth0

    client = get_auth0_client()
    if client is None:
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

    user = get_or_create_user_from_auth0(userinfo)
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
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
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
    return render(request, "accounts/signup.html", {"form": form})


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


@login_required
@require_http_methods(["GET", "POST"])
def profile_setup(request):
    if request.user.onboarding_completed:
        return redirect("accounts:profile", username=request.user.username)
    if request.method == "POST":
        form = ProfileSetupForm(request.POST, instance=request.user)
        if form.is_valid():
            user = form.save(commit=False)
            user.onboarding_completed = True
            user.save()
            messages.success(request, _("Your profile is ready. Welcome to PredictStamp!"))
            return redirect("accounts:onboarding")
    else:
        form = ProfileSetupForm(instance=request.user)
    return render(request, "accounts/profile_setup.html", {"form": form})


@login_required
def onboarding(request):
    """Activation step: nudge a brand-new user toward their first forecast.

    The wizard 'completes' when the user makes a forecast — so we surface popular
    open markets and a few sharp predictors to follow. Users who already have an
    open/resolved prediction are sent straight to their profile.
    """
    from accounts.selectors import get_top_predictors
    from markets.selectors import get_popular_open_markets

    profile = getattr(request.user, "profile", None)
    if profile and profile.prediction_count > 0:
        return redirect("accounts:profile", username=request.user.username)

    suggested_markets = get_popular_open_markets(limit=6)
    suggested_users = [
        leader.user
        for leader in get_top_predictors(8)
        if leader.user_id != request.user.id
    ][:5]
    following_ids = set(get_following_ids(request.user))

    return render(
        request,
        "accounts/onboarding.html",
        {
            "suggested_markets": suggested_markets,
            "suggested_users": suggested_users,
            "following_ids": following_ids,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def profile_edit(request):
    if request.method == "POST":
        form = ProfileEditForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            email_changed = "email" in form.changed_data
            user = form.save()
            if email_changed:
                mark_email_unverified(user)
                try:
                    send_verification_email(user)
                    messages.info(
                        request,
                        _("We sent a verification link to your new email address."),
                    )
                except Exception:
                    messages.error(
                        request,
                        _(
                            "Your email was updated, but we could not send a verification message. "
                            "Use the resend option on the verification page."
                        ),
                    )
                return redirect("accounts:verify_email_pending")
            messages.success(request, _("Profile updated."))
            return redirect("accounts:profile", username=request.user.username)
    else:
        form = ProfileEditForm(instance=request.user)
    return render(request, "accounts/profile_edit.html", {"form": form})


def user_search(request):
    query = request.GET.get("q", "").strip()
    search_ready = is_valid_user_search_query(query)
    results = search_user_matches(query=query) if search_ready else None
    return render(
        request,
        "accounts/user_search.html",
        {
            "search_query": query,
            "search_ready": search_ready,
            "users": results.users if results else [],
            "exact_users": results.exact_users if results else [],
            "similar_users": results.similar_users if results else [],
        },
    )


def user_search_partial(request):
    query = request.GET.get("q", "").strip()
    search_ready = is_valid_user_search_query(query)
    results = search_user_matches(query=query, limit=8) if search_ready else None
    return render(
        request,
        "accounts/partials/user_search_dropdown.html",
        {
            "search_query": query,
            "search_ready": search_ready,
            "users": results.users if results else [],
            "exact_users": results.exact_users if results else [],
            "similar_users": results.similar_users if results else [],
        },
    )


def profile_detail(request, username):
    user = get_object_or_404(
        User.objects.select_related("profile", "activity_streak"),
        username=username,
    )
    predictions = get_user_prediction_history(user)
    category_breakdown = get_user_category_breakdown(user)
    streak = getattr(user, "activity_streak", None)
    from accounts.achievement_services import (
        get_level_progress,
        get_pop_level_progress,
        get_user_achievements,
    )

    profile = getattr(user, "profile", None)
    level = get_level_progress(getattr(profile, "reputation_points", 0))
    pop_level = get_pop_level_progress(getattr(profile, "popularity_points", 0))
    achievements = get_user_achievements(user)
    earned_badges = [
        (achievement, awarded_at)
        for achievement, awarded_at, unlocked in achievements
        if unlocked
    ]
    unlocked_count = len(earned_badges)
    return render(
        request,
        "accounts/profile_detail.html",
        {
            "profile_user": user,
            "predictions": predictions,
            "category_breakdown": category_breakdown,
            "is_following": is_following(follower=request.user, following_user=user),
            "follower_count": get_follower_count(user),
            "following_count": get_following_count(user),
            "streak_current": streak.display_streak() if streak else 0,
            "streak_longest": streak.longest_streak if streak else 0,
            "streak_at_risk": streak.is_at_risk() if streak else False,
            "level": level,
            "pop_level": pop_level,
            "achievements": achievements,
            "earned_badges": earned_badges,
            "achievements_unlocked": unlocked_count,
            "achievements_total": len(achievements),
        },
    )


@login_required
@require_POST
def bookmark_toggle(request):
    target_type = request.POST.get("target_type")
    target_id = request.POST.get("target_id")

    if target_type not in (Bookmark.TargetType.PREDICTION, Bookmark.TargetType.PULSE_POST):
        return HttpResponseBadRequest(_("Invalid bookmark target"))

    if target_type == Bookmark.TargetType.PREDICTION:
        from predictions.models import Prediction

        target = get_object_or_404(Prediction, pk=int(target_id))
        bookmark_template = "dashboard/partials/forecast_bookmark_button.html"
        bookmark_context = {
            "prediction": target,
            "is_bookmarked": is_bookmarked(
                request.user,
                target_type,
                target.id,
            ),
        }
    else:
        from pulse.models import Post

        target = get_object_or_404(Post, pk=int(target_id))
        bookmark_template = "forum/partials/bookmark_button.html"
        bookmark_context = {
            "post": target,
            "is_bookmarked": is_bookmarked(
                request.user,
                target_type,
                target.id,
            ),
        }

    toggle_bookmark(
        user=request.user,
        target_type=target_type,
        target_id=target.id,
    )

    if request.headers.get("HX-Request"):
        bookmark_context["is_bookmarked"] = is_bookmarked(
            request.user,
            target_type,
            target.id,
        )
        return render(
            request,
            bookmark_template,
            bookmark_context,
        )
    return redirect(request.META.get("HTTP_REFERER", "/"))


@login_required
def bookmarks_list(request):
    active_type = (request.GET.get("type") or "").strip()
    if active_type not in ("", Bookmark.TargetType.PREDICTION, Bookmark.TargetType.PULSE_POST):
        active_type = ""

    bookmark_items = build_bookmarks_page_items(
        user=request.user,
        target_type=active_type or None,
    )
    return render(
        request,
        "accounts/bookmarks.html",
        {
            "bookmark_items": bookmark_items,
            "active_type": active_type,
        },
    )


def _render_follow_button(request, profile_user):
    return render(
        request,
        "accounts/partials/follow_button.html",
        {
            "profile_user": profile_user,
            "is_following": is_following(
                follower=request.user,
                following_user=profile_user,
            ),
        },
    )


@require_POST
def follow_toggle(request):
    if not request.user.is_authenticated:
        from urllib.parse import urlencode

        login_url = f"{reverse('accounts:login')}?{urlencode({'next': request.path})}"
        from accounts.htmx_utils import redirect_response

        return redirect_response(request, login_url)

    username = request.POST.get("username")
    if not username:
        return HttpResponseBadRequest(_("Missing username"))

    target_user = get_object_or_404(User, username=username)
    try:
        is_following_now = toggle_follow(follower=request.user, following_user=target_user)
    except ValidationError as exc:
        if request.headers.get("HX-Request"):
            return HttpResponseBadRequest(str(exc))
        messages.error(request, str(exc))
        return redirect("accounts:profile", username=target_user.username)

    if is_following_now:
        messages.success(
            request,
            _("You are now following %(name)s.") % {"name": target_user.public_name},
        )
    else:
        messages.success(
            request,
            _("You unfollowed %(name)s.") % {"name": target_user.public_name},
        )

    if request.headers.get("HX-Request"):
        return _render_follow_button(request, target_user)
    return redirect("accounts:profile", username=target_user.username)


@login_required
@require_http_methods(["GET", "POST"])
def alert_settings(request):
    preferences = get_or_create_notification_preferences(request.user)
    if request.method == "POST":
        form = NotificationPreferenceForm(request.POST, instance=preferences)
        if form.is_valid():
            form.save()
            messages.success(request, _("Alert preferences saved."))
            return redirect("accounts:alert_settings")
    else:
        form = NotificationPreferenceForm(instance=preferences)
    return render(
        request,
        "accounts/alert_settings.html",
        {"form": form},
    )


@login_required
def notifications_list(request):
    notifications = get_user_notifications(user=request.user)
    return render(
        request,
        "accounts/notifications.html",
        {"notifications": notifications},
    )


@login_required
def notifications_dropdown(request):
    from accounts.nav_cache import get_cached_unread_notification_count

    notifications = get_recent_notifications(user=request.user, limit=8)
    return render(
        request,
        "accounts/partials/notifications_dropdown.html",
        {
            "recent_notifications": notifications,
            "unread_notification_count": get_cached_unread_notification_count(user=request.user),
        },
    )


@login_required
@require_POST
def notification_mark_read(request, notification_id):
    from accounts.models import Notification

    notification = get_object_or_404(Notification, pk=notification_id)
    mark_notification_read(notification=notification, user=request.user)

    if request.headers.get("HX-Request"):
        return render(
            request,
            "accounts/partials/notification_item.html",
            {"notification": notification},
        )
    return redirect("accounts:notifications")


@login_required
@require_POST
def notifications_mark_all_read(request):
    mark_all_notifications_read(user=request.user)
    messages.success(request, _("All notifications marked as read."))
    return redirect("accounts:notifications")
