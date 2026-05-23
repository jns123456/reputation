from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from comments.forms import CommentForm
from comments.models import Vote
from comments.selectors import (
    attach_comment_votes,
    collect_comment_ids,
    get_prediction_comment_threads,
    get_user_comment_votes,
)
from comments.services import cast_vote, create_comment, get_user_vote
from markets.models import Market
from predictions.models import Prediction


def _discussion_context(request, *, market, prediction):
    threads = get_prediction_comment_threads(prediction)
    comment_ids = collect_comment_ids(threads)
    vote_map = get_user_comment_votes(request.user, comment_ids)
    attach_comment_votes(threads, vote_map)
    return {
        "market": market,
        "prediction": prediction,
        "threads": threads,
    }


@login_required
@require_POST
def create_comment_view(request, slug):
    market = get_object_or_404(Market, slug=slug)
    form = CommentForm(request.POST)
    parent_id = request.POST.get("parent_comment")
    prediction_id = request.POST.get("prediction")

    if not form.is_valid():
        return HttpResponseBadRequest("Invalid comment")

    parent = None
    if parent_id:
        parent = market.comments.filter(pk=parent_id).first()

    prediction = None
    if prediction_id:
        prediction = get_object_or_404(Prediction, pk=prediction_id, market=market)
    elif parent and parent.prediction_id:
        prediction = parent.prediction

    if not prediction:
        return HttpResponseBadRequest("Comments must be posted on a forecast thread.")

    try:
        create_comment(
            user=request.user,
            market=market,
            body=form.cleaned_data["body"],
            parent_comment=parent,
            prediction=prediction,
        )
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))

    if request.headers.get("HX-Request"):
        return render(
            request,
            "comments/partials/prediction_discussion_inner.html",
            _discussion_context(request, market=market, prediction=prediction),
        )
    return redirect("markets:detail", slug=slug)


@login_required
@require_POST
def vote_view(request):
    target_type = request.POST.get("target_type")
    target_id = request.POST.get("target_id")
    value = int(request.POST.get("value", 0))

    if target_type not in (Vote.TargetType.COMMENT, Vote.TargetType.PREDICTION):
        return HttpResponseBadRequest("Invalid target type")

    try:
        cast_vote(
            user=request.user,
            target_type=target_type,
            target_id=int(target_id),
            value=value,
        )
    except ValueError as e:
        return HttpResponseBadRequest(str(e))

    if request.headers.get("HX-Request"):
        if target_type == Vote.TargetType.COMMENT:
            from comments.models import Comment

            comment = get_object_or_404(Comment, pk=int(target_id))
            user_vote = get_user_vote(request.user, target_type, int(target_id))
            return render(
                request,
                "comments/partials/vote_buttons.html",
                {
                    "target_type": Vote.TargetType.COMMENT,
                    "target_id": comment.id,
                    "score": comment.popularity_score,
                    "user_vote": user_vote.value if user_vote else 0,
                    "layout": request.POST.get("layout", "horizontal"),
                },
            )
        from predictions.models import Prediction

        prediction = get_object_or_404(Prediction, pk=int(target_id))
        user_vote = get_user_vote(request.user, target_type, int(target_id))
        return render(
            request,
            "comments/partials/vote_buttons.html",
            {
                "target_type": Vote.TargetType.PREDICTION,
                "target_id": prediction.id,
                "score": prediction.popularity_score,
                "user_vote": user_vote.value if user_vote else 0,
                "layout": request.POST.get("layout", "vertical"),
                "after_vote_focus": f"prediction-discussion-{prediction.id}",
            },
        )

    return redirect(request.META.get("HTTP_REFERER", "/"))


def comment_vote_partial(request, comment_id):
    from comments.models import Comment

    comment = get_object_or_404(Comment, pk=comment_id)
    user_vote = get_user_vote(request.user, Vote.TargetType.COMMENT, comment_id)
    return render(
        request,
        "comments/partials/vote_buttons.html",
        {
            "target_type": Vote.TargetType.COMMENT,
            "target_id": comment_id,
            "score": comment.popularity_score,
            "user_vote": user_vote.value if user_vote else 0,
            "layout": request.GET.get("layout", "horizontal"),
        },
    )
