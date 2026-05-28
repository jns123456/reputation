from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib import messages
from django.utils.translation import gettext as _
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from accounts.bookmark_selectors import is_bookmarked
from accounts.bookmark_services import toggle_bookmark
from accounts.bookmarks_services import build_bookmarks_page_items
from accounts.follow_selectors import get_follower_count, get_following_count, is_following
from accounts.follow_services import toggle_follow
from accounts.forms import NotificationPreferenceForm, ProfileEditForm, ProfileSetupForm, SignUpForm, AvatarUploadForm
from accounts.models import Bookmark, User
from accounts.category_selectors import get_user_category_breakdown
from accounts.notification_selectors import get_recent_notifications, get_user_notifications
from accounts.notification_services import (
    get_or_create_notification_preferences,
    mark_all_notifications_read,
    mark_notification_read,
    queue_login_notification_toast,
)
from accounts.selectors import get_user_prediction_history, search_users


class CustomLoginView(LoginView):
    template_name = "accounts/login.html"

    def get_success_url(self):
        if not self.request.user.onboarding_completed:
            return reverse("accounts:profile_setup")
        return reverse("accounts:profile", kwargs={"username": self.request.user.username})

    def form_valid(self, form):
        response = super().form_valid(form)
        queue_login_notification_toast(request=self.request)
        return response


class CustomLogoutView(LogoutView):
    next_page = "dashboard:landing"


def signup(request):
    if request.user.is_authenticated:
        if not request.user.onboarding_completed:
            return redirect("accounts:profile_setup")
        return redirect("accounts:profile", username=request.user.username)
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            queue_login_notification_toast(request=request)
            return redirect("accounts:profile_setup")
    else:
        form = SignUpForm()
    return render(request, "accounts/signup.html", {"form": form})


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
            return redirect("accounts:profile", username=user.username)
    else:
        form = ProfileSetupForm(instance=request.user)
    return render(request, "accounts/profile_setup.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def profile_edit(request):
    if request.method == "POST":
        form = ProfileEditForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, _("Profile updated."))
            return redirect("accounts:profile", username=request.user.username)
    else:
        form = ProfileEditForm(instance=request.user)
    return render(request, "accounts/profile_edit.html", {"form": form})


@login_required
@require_POST
def avatar_upload(request):
    form = AvatarUploadForm(request.POST, request.FILES)
    if form.is_valid():
        from accounts.avatar_services import update_user_avatar

        update_user_avatar(user=request.user, avatar=form.cleaned_data["avatar"])
        messages.success(request, _("Profile photo updated."))
    else:
        messages.error(request, form.errors.get("avatar", [_("Invalid profile photo.")])[0])

    if request.headers.get("HX-Request"):
        return render(
            request,
            "accounts/partials/profile_avatar_upload.html",
            {"profile_user": request.user},
        )
    return redirect("accounts:profile", username=request.user.username)


def user_search(request):
    query = request.GET.get("q", "").strip()
    users = search_users(query=query) if query else []
    return render(
        request,
        "accounts/user_search.html",
        {
            "search_query": query,
            "users": users,
        },
    )


def user_search_partial(request):
    query = request.GET.get("q", "").strip()
    users = search_users(query=query, limit=8)
    return render(
        request,
        "accounts/partials/user_search_dropdown.html",
        {
            "search_query": query,
            "users": users,
        },
    )


def profile_detail(request, username):
    user = get_object_or_404(User.objects.select_related("profile"), username=username)
    predictions = get_user_prediction_history(user)
    category_breakdown = get_user_category_breakdown(user)
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


@login_required
@require_POST
def follow_toggle(request):
    username = request.POST.get("username")
    if not username:
        return HttpResponseBadRequest(_("Missing username"))

    target_user = get_object_or_404(User, username=username)
    toggle_follow(follower=request.user, following_user=target_user)

    if request.headers.get("HX-Request"):
        return render(
            request,
            "accounts/partials/follow_button.html",
            {
                "profile_user": target_user,
                "is_following": is_following(
                    follower=request.user,
                    following_user=target_user,
                ),
            },
        )
    return redirect(request.META.get("HTTP_REFERER", "/"))


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
