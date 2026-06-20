"""Public profiles, user search, bookmarks, and follow lists."""

from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST, require_http_methods

from accounts import abuse_services
from accounts.account_deletion_services import AccountDeletionError, delete_user_account
from accounts.bookmark_selectors import is_bookmarked
from accounts.bookmark_services import toggle_bookmark
from accounts.bookmarks_services import build_bookmarks_page_items
from accounts.category_selectors import get_user_category_breakdown
from accounts.email_verification_services import (
    mark_email_unverified,
    send_verification_email,
)
from accounts.follow_selectors import (
    get_follower_count,
    get_followers,
    get_following_count,
    get_following_ids,
    get_following_users,
    is_following,
)
from accounts.follow_services import toggle_follow
from accounts.forms import AccountDeletionForm, ContestPayoutRequestForm, ProfileEditForm
from accounts.http_utils import enforce_ip_rate_limit, safe_redirect_to_referer
from accounts.models import Bookmark, User
from accounts.selectors import search_user_matches
from accounts.user_search_selectors import (
    BROWSABLE_USERS_PAGE_SIZE,
    count_browsable_users,
    get_browsable_users,
    is_valid_user_search_query,
)
from accounts.write_guard import write_guard_user_message
from predictions.selectors import get_user_closed_prediction_history


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


@login_required
@require_http_methods(["GET", "POST"])
def account_delete(request):
    form = AccountDeletionForm(user=request.user)
    if request.method == "POST":
        try:
            enforce_ip_rate_limit(request=request, action="account_deletion")
        except abuse_services.RateLimitExceeded:
            messages.error(
                request,
                _("Too many attempts. Please wait a few minutes and try again."),
            )
            return render(
                request,
                "accounts/account_delete.html",
                {"form": AccountDeletionForm(request.POST, user=request.user)},
            )

        if request.POST.get("action") == "send_code":
            from accounts.account_deletion_services import send_deletion_confirmation_code

            sent, message_text = send_deletion_confirmation_code(request.user)
            (messages.success if sent else messages.error)(request, message_text)
            return redirect("accounts:account_delete")

        form = AccountDeletionForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                delete_user_account(user=request.user)
            except AccountDeletionError as exc:
                messages.error(request, exc.message)
                return redirect("accounts:account_delete")

            logout(request)
            messages.success(request, _("Your account has been permanently deleted."))
            return redirect("dashboard:landing")

    return render(request, "accounts/account_delete.html", {"form": form})


def user_search(request):
    query = request.GET.get("q", "").strip()
    params = {"q": query} if query else {}
    return redirect(f"{reverse('accounts:user_list')}?{urlencode(params)}" if params else reverse("accounts:user_list"))


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


@login_required
def mention_suggestions_partial(request):
    """HTMX/JSON-ish partial: followed users matching an @-mention prefix."""
    from accounts.mention_selectors import search_following_for_mention

    query = request.GET.get("q", "").strip()
    users = search_following_for_mention(user=request.user, prefix=query, limit=8)
    return render(
        request,
        "accounts/partials/mention_suggestions_dropdown.html",
        {
            "users": users,
            "query": query.lstrip("@"),
        },
    )


def user_list(request):
    query = request.GET.get("q", "").strip()
    search_ready = is_valid_user_search_query(query)
    following_ids = (
        set(get_following_ids(request.user)) if request.user.is_authenticated else set()
    )

    if query:
        results = search_user_matches(query=query) if search_ready else None
        return render(
            request,
            "accounts/user_list.html",
            {
                "search_query": query,
                "search_ready": search_ready,
                "users": results.users if results else [],
                "exact_users": results.exact_users if results else [],
                "similar_users": results.similar_users if results else [],
                "following_ids": following_ids,
                "is_searching": True,
            },
        )

    try:
        offset = max(0, int(request.GET.get("offset", 0)))
    except (TypeError, ValueError):
        offset = 0

    users = get_browsable_users(offset=offset)
    total_count = count_browsable_users()
    next_offset = offset + BROWSABLE_USERS_PAGE_SIZE
    prev_offset = max(0, offset - BROWSABLE_USERS_PAGE_SIZE)

    return render(
        request,
        "accounts/user_list.html",
        {
            "users": users,
            "total_count": total_count,
            "offset": offset,
            "has_next": next_offset < total_count,
            "has_prev": offset > 0,
            "next_offset": next_offset,
            "prev_offset": prev_offset,
            "following_ids": following_ids,
            "search_query": "",
            "is_searching": False,
        },
    )


def profile_detail(request, username):
    user = get_object_or_404(
        User.objects.select_related("profile", "activity_streak", "creator_program"),
        username=username,
    )
    predictions = get_user_closed_prediction_history(user, limit=10)
    from predictions.selectors import get_user_prediction_summary

    prediction_summary = get_user_prediction_summary(user)
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
        (achievement, awarded_at, count)
        for achievement, awarded_at, unlocked, count in achievements
        if unlocked
    ]
    unlocked_count = sum(1 for _achievement, _at, unlocked, _count in achievements if unlocked)
    from predictions.selectors import get_user_calibration
    from reputation.season_services import get_user_season_awards
    from reputation.services import calculate_user_unrealized_reputation

    calibration = get_user_calibration(user)
    has_calibration_data = any(row["total"] for row in calibration)

    return render(
        request,
        "accounts/profile_detail.html",
        {
            "calibration": calibration,
            "has_calibration_data": has_calibration_data,
            "season_awards": get_user_season_awards(user),
            "profile_user": user,
            "predictions": predictions,
            "prediction_summary": prediction_summary,
            "unrealized_reputation": calculate_user_unrealized_reputation(user),
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
    return safe_redirect_to_referer(request, fallback="/")


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


def _render_follow_button(request, profile_user, *, context="profile"):
    template = (
        "accounts/partials/follow_button_list.html"
        if context == "list"
        else "accounts/partials/follow_button.html"
    )
    context_data = {
        "profile_user": profile_user,
        "is_following": is_following(
            follower=request.user,
            following_user=profile_user,
        ),
    }
    if context == "list":
        context_data["following_ids"] = (
            set(get_following_ids(request.user)) if request.user.is_authenticated else set()
        )
    return render(request, template, context_data)


def _render_profile_connections(request, *, profile_user, users, active_tab):
    following_ids = (
        set(get_following_ids(request.user)) if request.user.is_authenticated else set()
    )
    return render(
        request,
        "accounts/profile_connections.html",
        {
            "profile_user": profile_user,
            "users": users,
            "active_tab": active_tab,
            "follower_count": get_follower_count(profile_user),
            "following_count": get_following_count(profile_user),
            "following_ids": following_ids,
        },
    )


def profile_followers(request, username):
    profile_user = get_object_or_404(
        User.objects.select_related("profile"),
        username=username,
    )
    return _render_profile_connections(
        request,
        profile_user=profile_user,
        users=get_followers(profile_user),
        active_tab="followers",
    )


def profile_following(request, username):
    profile_user = get_object_or_404(
        User.objects.select_related("profile"),
        username=username,
    )
    return _render_profile_connections(
        request,
        profile_user=profile_user,
        users=get_following_users(profile_user),
        active_tab="following",
    )


@login_required
@require_http_methods(["GET", "POST"])
def profile_contest_earnings(request, username):
    profile_user = get_object_or_404(User, username=username)
    if request.user != profile_user:
        return redirect("accounts:profile", username=username)

    from reputation.payout_services import (
        contest_payouts_enabled,
        create_payout_request,
        get_contest_earnings_summary,
        get_user_contest_wins,
        get_user_payout_requests,
        minimum_payout_usd,
        PayoutRequestError,
        user_has_pending_payout_request,
    )

    summary = get_contest_earnings_summary(profile_user)
    minimum_usd = minimum_payout_usd()
    can_request = (
        contest_payouts_enabled()
        and summary["available_usd"] >= minimum_usd
        and not user_has_pending_payout_request(profile_user)
    )

    if request.method == "POST":
        if not can_request:
            messages.error(request, _("Withdrawal requests are not available right now."))
            return redirect("accounts:profile_contest_earnings", username=username)

        form = ContestPayoutRequestForm(
            request.POST,
            available_usd=summary["available_usd"],
            minimum_usd=minimum_usd,
        )
        if form.is_valid():
            try:
                create_payout_request(
                    user=profile_user,
                    amount_usd=form.cleaned_data["amount_usd"],
                    usdc_address=form.cleaned_data["usdc_address"],
                )
            except PayoutRequestError as exc:
                messages.error(request, exc.message)
            else:
                messages.success(
                    request,
                    _(
                        "Withdrawal request submitted. We will send USDC to your address after review."
                    ),
                )
                return redirect("accounts:profile_contest_earnings", username=username)
    else:
        initial_amount = summary["available_usd"] if can_request else None
        form = ContestPayoutRequestForm(
            available_usd=summary["available_usd"],
            minimum_usd=minimum_usd,
            initial={"amount_usd": initial_amount} if initial_amount else None,
        )

    return render(
        request,
        "accounts/profile_contest_earnings.html",
        {
            "profile_user": profile_user,
            "summary": summary,
            "minimum_usd": minimum_usd,
            "contest_wins": get_user_contest_wins(profile_user),
            "payout_requests": get_user_payout_requests(profile_user),
            "form": form,
            "can_request_payout": can_request,
            "has_pending_payout": user_has_pending_payout_request(profile_user),
            "payouts_enabled": contest_payouts_enabled(),
        },
    )

