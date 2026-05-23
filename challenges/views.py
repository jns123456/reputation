from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

import json

from challenges.forms import ChallengeCreateForm
from challenges.models import MAX_CHALLENGE_MARKETS, Challenge, ChallengeParticipant
from challenges.selectors import (
    get_challenge_event_progress,
    get_challenge_for_user,
    get_challenge_markets,
    get_challenge_resolution_snapshots,
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
                messages.success(request, "Challenge created. Waiting for opponents to accept.")
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
        str(market.id): market.title
        for market in initial_markets
        if market.id in selected_ids_int
    }

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
    standings = get_challenge_standings(challenge)
    markets = get_challenge_markets(challenge)

    return render(
        request,
        "challenges/challenge_detail.html",
        {
            "challenge": challenge,
            "participation": participation,
            "standings": standings,
            "markets": markets,
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
        messages.success(request, "You joined the challenge.")
    except ValidationError as exc:
        messages.error(request, exc.messages[0] if exc.messages else str(exc))
    return redirect("challenges:detail", pk=pk)


@login_required
@require_POST
def challenge_decline(request, pk):
    challenge = get_object_or_404(Challenge, pk=pk)
    try:
        decline_challenge(challenge=challenge, user=request.user)
        messages.info(request, "You declined the challenge.")
    except ValidationError as exc:
        messages.error(request, exc.messages[0] if exc.messages else str(exc))
    return redirect("challenges:list")


@login_required
@require_POST
def challenge_cancel(request, pk):
    challenge = get_object_or_404(Challenge, pk=pk, creator=request.user)
    try:
        cancel_challenge(challenge=challenge, user=request.user)
        messages.info(request, "Challenge cancelled.")
    except ValidationError as exc:
        messages.error(request, exc.messages[0] if exc.messages else str(exc))
    return redirect("challenges:list")
