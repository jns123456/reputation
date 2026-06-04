"""Profile setup and first-run onboarding views."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from accounts.follow_selectors import get_following_ids
from accounts.forms import ProfileSetupForm
from accounts.models import User


def _apply_onboarding_classification(user, form):
    """Set account_type + verification_status from the onboarding answers (§15/§16)."""
    from accounts.agent_services import classify_account_from_onboarding
    from accounts.risk_services import calculate_account_risk_score, risk_band

    operation = form.cleaned_data.get("account_operation", "human")
    user.account_type = classify_account_from_onboarding(operation)

    # Progressive friction: high-risk new accounts are flagged for review.
    band = risk_band(calculate_account_risk_score(user))
    if band == "high":
        user.account_type = User.AccountType.SUSPICIOUS
        user.verification_status = User.VerificationStatus.RESTRICTED
    elif user.is_email_verified:
        user.verification_status = User.VerificationStatus.EMAIL_VERIFIED


def _finalize_agent_onboarding(user, form):
    """Create the agent trust profile for declared/organization agents (§15)."""
    from accounts.agent_services import get_or_create_agent_profile, requires_agent_disclosure

    if not requires_agent_disclosure(user.account_type):
        return
    get_or_create_agent_profile(
        user,
        agent_operator=form.cleaned_data.get("agent_operator", ""),
        public_description=form.cleaned_data.get("agent_public_description", ""),
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
            _apply_onboarding_classification(user, form)
            user.save()
            _finalize_agent_onboarding(user, form)
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

