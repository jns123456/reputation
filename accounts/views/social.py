"""Follow toggles, bookmarks, and notification views."""

from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST, require_http_methods

from accounts import abuse_services
from accounts.follow_selectors import get_following_ids, is_following
from accounts.follow_services import toggle_follow
from accounts.forms import NotificationPreferenceForm
from accounts.htmx_utils import redirect_response
from accounts.models import User
from accounts.notification_selectors import get_user_notifications
from accounts.notification_services import (
    get_or_create_notification_preferences,
    mark_notification_read,
)
from accounts.views.profile import _render_follow_button
from accounts.write_guard import write_guard_user_message


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

    context = request.POST.get("context", "profile")
    target_user = get_object_or_404(User, username=username)
    try:
        is_following_now = toggle_follow(follower=request.user, following_user=target_user)
    except ValidationError as exc:
        if request.headers.get("HX-Request"):
            return HttpResponseBadRequest(str(exc))
        messages.error(request, str(exc))
        if context == "list":
            return redirect("accounts:user_list")
        return redirect("accounts:profile", username=target_user.username)
    except abuse_services.RateLimitExceeded as exc:
        message = write_guard_user_message(exc)
        if request.headers.get("HX-Request"):
            return HttpResponseBadRequest(message, status=429)
        messages.error(request, message)
        if context == "list":
            return redirect("accounts:user_list")
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
        return _render_follow_button(request, target_user, context=context)
    if context == "list":
        return redirect("accounts:user_list")
    return redirect("accounts:profile", username=target_user.username)


@require_POST
def topic_follow_toggle(request):
    """Follow/unfollow a canonical market category (HTMX-friendly)."""
    if not request.user.is_authenticated:
        login_url = f"{reverse('accounts:login')}?{urlencode({'next': request.POST.get('next', '/')})}"
        return redirect_response(request, login_url)

    category_slug = request.POST.get("category_slug", "").strip()
    if not category_slug:
        return HttpResponseBadRequest(_("Missing topic"))

    from accounts.follow_services import toggle_topic_follow

    try:
        is_following_now = toggle_topic_follow(user=request.user, category_slug=category_slug)
    except ValidationError as exc:
        return HttpResponseBadRequest(str(exc))
    except abuse_services.RateLimitExceeded as exc:
        return HttpResponseBadRequest(write_guard_user_message(exc), status=429)

    if request.headers.get("HX-Request"):
        return render(
            request,
            "accounts/partials/topic_follow_button.html",
            {"category_slug": category_slug, "is_following_topic": is_following_now},
        )
    return redirect(request.POST.get("next") or "markets:list")


@require_POST
def market_watch_toggle(request, slug):
    """Watch/unwatch a market (HTMX-friendly)."""
    if not request.user.is_authenticated:
        login_url = f"{reverse('accounts:login')}?{urlencode({'next': reverse('markets:detail', kwargs={'slug': slug})})}"
        return redirect_response(request, login_url)

    from markets.models import Market

    market = get_object_or_404(Market, slug=slug)

    from accounts.follow_services import toggle_market_watch

    try:
        is_watching_now = toggle_market_watch(user=request.user, market=market)
    except abuse_services.RateLimitExceeded as exc:
        return HttpResponseBadRequest(write_guard_user_message(exc), status=429)

    if request.headers.get("HX-Request"):
        return render(
            request,
            "accounts/partials/market_watch_button.html",
            {"market": market, "is_watching_market": is_watching_now},
        )
    return redirect("markets:detail", slug=market.slug)


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
    from accounts.nav_cache import (
        get_cached_recent_notifications,
        get_cached_unread_notification_count,
    )

    return render(
        request,
        "accounts/partials/notifications_dropdown.html",
        {
            "recent_notifications": get_cached_recent_notifications(
                user=request.user,
                limit=8,
            ),
            "unread_notification_count": get_cached_unread_notification_count(user=request.user),
        },
    )


@login_required
def notification_open(request, notification_id):
    from accounts.models import Notification

    notification = get_object_or_404(
        Notification, pk=notification_id, recipient=request.user
    )
    mark_notification_read(notification=notification, user=request.user)
    return redirect(notification.action_url)


@login_required
@require_POST
def notification_mark_read(request, notification_id):
    from accounts.models import Notification

    # Scope the lookup to the recipient: cross-user probes get a 404 instead
    # of reaching the service layer (which would raise an unhandled 500).
    notification = get_object_or_404(
        Notification, pk=notification_id, recipient=request.user
    )
    mark_notification_read(notification=notification, user=request.user)

    if request.headers.get("HX-Request"):
        return render(
            request,
            "accounts/partials/notification_item.html",
            {"notification": notification},
        )
    return redirect("accounts:notifications")
