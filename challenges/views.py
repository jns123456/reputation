from django.contrib import messages
from django.utils import timezone
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

import json

from challenges.forms import ChallengeCreateForm
from challenges.models import MAX_CHALLENGE_MARKETS, Challenge, ChallengeParticipant
from markets.models import Market
from predictions.models import Prediction
from reputation.services import calculate_exit_reputation_delta
from challenges.selectors import (
    get_challenge_event_progress,
    get_challenge_for_user,
    get_challenge_markets,
    get_challenge_resolution_snapshots,
    get_challenge_leaderboard,
    get_challenge_standings,
    get_pending_challenge_invitations,
    get_user_challenges,
    get_user_participation,
    search_open_markets_for_challenge,
)
from challenges.services import (
    accept_challenge,
    cancel_challenge,
    create_challenge,
    decline_challenge,
)


def _sort_challenge_markets_by_expiration(markets):
    """Soonest close_date first; events without a date last."""
    far_future = timezone.now().replace(year=9999, month=12, day=31)

    def sort_key(market):
        if market.close_date:
            return (0, market.close_date)
        return (1, far_future)

    return sorted(markets, key=sort_key)


@login_required
def challenge_list(request):
    status_filter = request.GET.get("status", "")
    challenges = get_user_challenges(request.user)
    if status_filter:
        challenges = challenges.filter(status=status_filter)

    pending_invitations = get_pending_challenge_invitations(request.user)

    return render(
        request,
        "challenges/challenge_list.html",
        {
            "challenges": challenges,
            "current_status": status_filter,
            "pending_invitations": pending_invitations,
            "status_choices": Challenge.Status.choices,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def challenge_create(request):
    from accounts.follow_selectors import get_mutual_followers

    mutual_followers = get_mutual_followers(request.user)

    if request.method == "POST":
        form = ChallengeCreateForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                challenge = create_challenge(
                    creator=request.user,
                    title=form.cleaned_data.get("title", ""),
                    market_ids=[m.id for m in form.cleaned_data["markets"]],
                    opponent_ids=[int(uid) for uid in form.cleaned_data["opponents"]],
                )
                messages.success(request, _("Challenge created. Waiting for opponents to accept."))
                return redirect("challenges:detail", pk=challenge.pk)
            except ValidationError as exc:
                if hasattr(exc, "message_dict"):
                    for field, errors in exc.message_dict.items():
                        for error in errors:
                            form.add_error(field if field in form.fields else None, error)
                else:
                    form.add_error(None, exc.messages[0] if exc.messages else str(exc))
    else:
        form = ChallengeCreateForm(user=request.user)

    selected_market_ids = []
    if request.method == "POST":
        selected_market_ids = request.POST.getlist("markets")
    selected_ids_int = [int(pk) for pk in selected_market_ids if str(pk).isdigit()]
    initial_markets = search_open_markets_for_challenge(
        query="",
        selected_ids=selected_ids_int,
    )
    selected_market_titles = {
        str(market.id): market.display_title
        for market in initial_markets
        if market.id in selected_ids_int
    }

    initial_step = 1
    if request.method == "POST" and form.errors and not form.errors.get("opponents"):
        initial_step = 2

    return render(
        request,
        "challenges/challenge_create.html",
        {
            "form": form,
            "mutual_followers": mutual_followers,
            "initial_markets": initial_markets,
            "selected_market_ids_json": json.dumps(selected_ids_int),
            "selected_market_titles_json": json.dumps(selected_market_titles),
            "selected_market_ids": set(selected_ids_int),
            "max_challenge_markets": MAX_CHALLENGE_MARKETS,
            "initial_step": initial_step,
        },
    )


@login_required
def challenge_market_search(request):
    query = request.GET.get("q", "").strip()
    selected_ids = request.GET.getlist("selected")
    markets = search_open_markets_for_challenge(
        query=query,
        selected_ids=selected_ids,
    )
    selected_set = {int(pk) for pk in selected_ids if str(pk).isdigit()}
    return render(
        request,
        "challenges/partials/market_picker_list.html",
        {
            "markets": markets,
            "selected_market_ids": selected_set,
            "search_query": query,
        },
    )


@login_required
def challenge_detail(request, pk):
    challenge = get_challenge_for_user(challenge_id=pk, user=request.user)
    if not challenge:
        raise Http404("Challenge not found.")

    participation = get_user_participation(challenge=challenge, user=request.user)
    standings = get_challenge_leaderboard(challenge)
    markets = get_challenge_markets(challenge)
    markets = _sort_challenge_markets_by_expiration(markets)
    user_market_forecasts = {}
    if request.user.is_authenticated and markets:
        market_ids = [market.id for market in markets]
        pending = Prediction.objects.filter(
            user=request.user,
            market_id__in=market_ids,
            status=Prediction.Status.PENDING,
        )
        user_market_forecasts = {prediction.market_id: prediction for prediction in pending}
    for market in markets:
        forecast = user_market_forecasts.get(market.id)
        market.user_forecast = forecast
        if forecast and market.status == Market.Status.OPEN:
            market.user_forecast_unrealized = calculate_exit_reputation_delta(
                predicted_outcome=forecast.predicted_outcome,
                entry_probability_snapshot=forecast.probability_at_prediction_time,
                exit_probability_snapshot=market.current_probability or {},
                predicted_direction=forecast.predicted_direction,
            )
        else:
            market.user_forecast_unrealized = None

    event_filter_counts = {
        "all": len(markets),
        "voted": sum(1 for market in markets if market.user_forecast),
        "pending": sum(
            1
            for market in markets
            if not market.user_forecast and market.status == Market.Status.OPEN
        ),
    }

    leaderboard_totals = {
        "realized": sum(row["realized_points"] for row in standings),
        "unrealized": sum(row["unrealized_points"] for row in standings),
        "total": sum(row["total_points"] for row in standings),
    }

    return render(
        request,
        "challenges/challenge_detail.html",
        {
            "challenge": challenge,
            "participation": participation,
            "standings": standings,
            "leaderboard_totals": leaderboard_totals,
            "markets": markets,
            "event_filter_counts": event_filter_counts,
            "event_progress": get_challenge_event_progress(challenge),
            "resolution_snapshots": get_challenge_resolution_snapshots(challenge),
            "is_creator": challenge.creator_id == request.user.id,
        },
    )


@login_required
@require_POST
def challenge_accept(request, pk):
    challenge = get_object_or_404(Challenge, pk=pk)
    try:
        accept_challenge(challenge=challenge, user=request.user)
        messages.success(request, _("You joined the challenge."))
    except ValidationError as exc:
        messages.error(request, exc.messages[0] if exc.messages else str(exc))
    return redirect("challenges:detail", pk=pk)


@login_required
@require_POST
def challenge_decline(request, pk):
    challenge = get_object_or_404(Challenge, pk=pk)
    try:
        decline_challenge(challenge=challenge, user=request.user)
        messages.info(request, _("You declined the challenge."))
    except ValidationError as exc:
        messages.error(request, exc.messages[0] if exc.messages else str(exc))
    return redirect("challenges:list")


@login_required
@require_POST
def challenge_cancel(request, pk):
    challenge = get_object_or_404(Challenge, pk=pk, creator=request.user)
    try:
        cancel_challenge(challenge=challenge, user=request.user)
        messages.info(request, _("Challenge cancelled."))
    except ValidationError as exc:
        messages.error(request, exc.messages[0] if exc.messages else str(exc))
    return redirect("challenges:list")
