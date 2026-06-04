"""Creator program setup, subscribers, and membership actions."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods, require_POST

from accounts import abuse_services
from accounts.http_utils import safe_redirect_to_referer
from accounts.models import User
from accounts.monetization_forms import CreatorProgramForm
from accounts.monetization_selectors import get_active_subscribers, get_creator_program_or_none
from accounts.monetization_services import (
    count_active_subscribers,
    get_or_create_creator_program,
    subscribe_to_creator,
    unsubscribe_from_creator,
    update_creator_program,
)
from accounts.write_guard import ContentRejected, write_guard_user_message


def _monetize_context(request, profile_user):
    program = get_creator_program_or_none(profile_user)
    is_profile_owner = request.user.is_authenticated and request.user.pk == profile_user.pk
    is_subscribed = False
    if request.user.is_authenticated and not is_profile_owner and program and program.is_enabled:
        from accounts.monetization_services import is_active_subscriber

        is_subscribed = is_active_subscriber(viewer=request.user, creator=profile_user)

    subscriber_count = count_active_subscribers(profile_user) if program and program.is_enabled else 0

    premium_forecasts = 0
    premium_posts = 0
    if is_profile_owner and program:
        from accounts.models import SubscriberAudience
        from predictions.models import Prediction
        from pulse.models import Post

        premium_forecasts = Prediction.objects.filter(
            user=profile_user,
            audience=SubscriberAudience.SUBSCRIBERS,
        ).count()
        premium_posts = Post.objects.filter(
            user=profile_user,
            audience=SubscriberAudience.SUBSCRIBERS,
        ).count()

    return {
        "profile_user": profile_user,
        "is_profile_owner": is_profile_owner,
        "creator_program": program,
        "is_subscribed": is_subscribed,
        "subscriber_count": subscriber_count,
        "premium_forecast_count": premium_forecasts,
        "premium_post_count": premium_posts,
    }


@login_required
@require_http_methods(["GET", "POST"])
def creator_setup(request, username):
    profile_user = get_object_or_404(User, username=username)
    if request.user.pk != profile_user.pk:
        return redirect("accounts:profile", username=username)

    program = get_or_create_creator_program(profile_user)

    if request.method == "POST":
        form = CreatorProgramForm(request.POST, program=program)
        if form.is_valid():
            price = form.cleaned_data["monthly_price"]
            cents = int(round(float(price) * 100))
            update_creator_program(
                user=profile_user,
                is_enabled=form.cleaned_data["is_enabled"],
                tagline=form.cleaned_data["tagline"],
                welcome_message=form.cleaned_data["welcome_message"],
                monthly_price_cents=cents,
            )
            messages.success(request, _("Creator program saved."))
            return redirect("accounts:profile_monetize", username=username)
    else:
        form = CreatorProgramForm(program=program)

    return render(
        request,
        "accounts/creator_setup.html",
        {
            "profile_user": profile_user,
            "form": form,
            "program": program,
        },
    )


@login_required
def creator_subscribers(request, username):
    profile_user = get_object_or_404(User, username=username)
    if request.user.pk != profile_user.pk:
        return redirect("accounts:profile", username=username)

    program = get_creator_program_or_none(profile_user)
    subscribers = get_active_subscribers(profile_user) if program and program.is_enabled else []

    return render(
        request,
        "accounts/creator_subscribers.html",
        {
            "profile_user": profile_user,
            "program": program,
            "subscribers": subscribers,
            "subscriber_count": len(subscribers),
        },
    )


def profile_monetize(request, username):
    profile_user = get_object_or_404(
        User.objects.select_related("creator_program"),
        username=username,
    )
    return render(
        request,
        "accounts/profile_monetize.html",
        _monetize_context(request, profile_user),
    )


@login_required
@require_POST
def creator_subscribe(request):
    creator_id = request.POST.get("creator_id")
    if not creator_id:
        return HttpResponseBadRequest(_("Missing creator."))

    creator = get_object_or_404(User, pk=int(creator_id))
    try:
        subscribe_to_creator(subscriber=request.user, creator=creator)
    except (ValidationError, ContentRejected) as exc:
        messages.error(request, write_guard_user_message(exc))
    except abuse_services.RateLimitExceeded as exc:
        messages.error(request, write_guard_user_message(exc))
    else:
        messages.success(
            request,
            _("You are now subscribed. Subscriber-only content from this creator is unlocked."),
        )

    return safe_redirect_to_referer(
        request,
        fallback=reverse("accounts:profile_monetize", kwargs={"username": creator.username}),
    )


@login_required
@require_POST
def creator_unsubscribe(request):
    creator_id = request.POST.get("creator_id")
    if not creator_id:
        return HttpResponseBadRequest(_("Missing creator."))

    creator = get_object_or_404(User, pk=int(creator_id))
    unsubscribe_from_creator(subscriber=request.user, creator=creator)
    messages.info(request, _("Subscription cancelled."))
    return safe_redirect_to_referer(
        request,
        fallback=reverse("accounts:profile_monetize", kwargs={"username": creator.username}),
    )
