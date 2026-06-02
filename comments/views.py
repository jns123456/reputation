from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest
from django.utils.translation import gettext as _
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from comments.forms import CommentForm
from comments.models import Vote
from comments.selectors import (
    attach_comment_votes,
    collect_comment_ids,
    get_prediction_comment_threads,
    get_target_vote_counts,
    get_target_voters,
    get_user_comment_votes,
    get_vote_previews_for_targets,
)
from comments.services import cast_vote, create_comment, get_user_vote
from markets.models import Market
from predictions.models import Prediction

from accounts import abuse_services
from accounts.http_utils import safe_redirect_to_referer
from accounts.write_guard import ContentRejected, write_guard_user_message


def _vote_preview_context(*, target_type, target_id, like_count=0, dislike_count=0):
    previews = get_vote_previews_for_targets(
        target_type=target_type,
        target_ids=[target_id],
    )
    preview = previews.get(target_id, {"likes": [], "dislikes": []})
    return {
        "like_preview": preview["likes"],
        "dislike_preview": preview["dislikes"],
        "like_count": like_count,
        "dislike_count": dislike_count,
        "target_type": target_type,
        "target_id": target_id,
    }


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
        return HttpResponseBadRequest(_("Invalid comment"))

    parent = None
    if parent_id:
        parent = market.comments.filter(pk=parent_id).first()

    prediction = None
    if prediction_id:
        prediction = get_object_or_404(Prediction, pk=prediction_id, market=market)
    elif parent and parent.prediction_id:
        prediction = parent.prediction

    if not prediction:
        return HttpResponseBadRequest(_("Comments must be posted on a forecast thread."))

    try:
        create_comment(
            user=request.user,
            market=market,
            body=form.cleaned_data["body"],
            parent_comment=parent,
            prediction=prediction,
        )
    except (ValueError, ContentRejected) as exc:
        return HttpResponseBadRequest(write_guard_user_message(exc))
    except abuse_services.RateLimitExceeded as exc:
        return HttpResponseBadRequest(write_guard_user_message(exc), status=429)

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

    if target_type not in (
        Vote.TargetType.COMMENT,
        Vote.TargetType.PREDICTION,
        Vote.TargetType.PULSE_POST,
        Vote.TargetType.PULSE_COMMENT,
    ):
        return HttpResponseBadRequest(_("Invalid target type"))

    try:
        existing_vote = get_user_vote(request.user, target_type, int(target_id))
        if existing_vote and existing_vote.value == value and value != 0:
            value = 0

        cast_vote(
            user=request.user,
            target_type=target_type,
            target_id=int(target_id),
            value=value,
        )
    except ValueError as e:
        return HttpResponseBadRequest(str(e))
    except abuse_services.RateLimitExceeded as exc:
        return HttpResponseBadRequest(write_guard_user_message(exc), status=429)

    if request.headers.get("HX-Request"):
        if target_type == Vote.TargetType.COMMENT:
            from comments.models import Comment

            comment = get_object_or_404(Comment, pk=int(target_id))
            user_vote = get_user_vote(request.user, target_type, int(target_id))
            like_count, dislike_count = get_target_vote_counts(
                target_type=target_type,
                target_id=comment.id,
            )
            return render(
                request,
                "comments/partials/vote_block.html",
                {
                    "target_type": Vote.TargetType.COMMENT,
                    "target_id": comment.id,
                    "score": comment.popularity_score,
                    "user_vote": user_vote.value if user_vote else 0,
                    "layout": request.POST.get("layout", "horizontal"),
                    "after_vote_focus": request.POST.get("after_vote_focus"),
                    **_vote_preview_context(
                        target_type=target_type,
                        target_id=comment.id,
                        like_count=like_count,
                        dislike_count=dislike_count,
                    ),
                },
            )
        if target_type == Vote.TargetType.PULSE_COMMENT:
            from pulse.selectors import get_comment_with_interactions

            comment = get_comment_with_interactions(int(target_id))
            if comment is None:
                from pulse.models import Comment as PulseComment

                raise PulseComment.DoesNotExist
            user_vote = get_user_vote(request.user, target_type, int(target_id))
            layout = request.POST.get("layout", "forum")
            if layout == "forum":
                return render(
                    request,
                    "forum/partials/comment_vote_preview_oob.html",
                    {
                        "comment": comment,
                        "post": comment.post,
                        "comment_vote": user_vote.value if user_vote else 0,
                        "vote_oob": True,
                        **_vote_preview_context(
                            target_type=target_type,
                            target_id=comment.id,
                            like_count=comment.like_count,
                            dislike_count=comment.dislike_count,
                        ),
                    },
                )
            return render(
                request,
                "comments/partials/vote_block.html",
                {
                    "target_type": Vote.TargetType.PULSE_COMMENT,
                    "target_id": comment.id,
                    "score": comment.popularity_score,
                    "user_vote": user_vote.value if user_vote else 0,
                    "layout": layout,
                    **_vote_preview_context(
                        target_type=target_type,
                        target_id=comment.id,
                        like_count=comment.like_count,
                        dislike_count=comment.dislike_count,
                    ),
                },
            )
        if target_type == Vote.TargetType.PULSE_POST:
            from pulse.selectors import get_post_with_interactions

            post = get_post_with_interactions(int(target_id))
            if post is None:
                from pulse.models import Post

                raise Post.DoesNotExist
            user_vote = get_user_vote(request.user, target_type, int(target_id))
            layout = request.POST.get("layout", "forum")
            if layout == "forum":
                return render(
                    request,
                    "forum/partials/vote_preview_oob.html",
                    {
                        "post": post,
                        "post_vote": user_vote.value if user_vote else 0,
                        "vote_oob": True,
                        **_vote_preview_context(
                            target_type=target_type,
                            target_id=post.id,
                            like_count=post.like_count,
                            dislike_count=post.dislike_count,
                        ),
                    },
                )
            return render(
                request,
                "comments/partials/vote_block.html",
                {
                    "target_type": Vote.TargetType.PULSE_POST,
                    "target_id": post.id,
                    "score": post.popularity_score,
                    "user_vote": user_vote.value if user_vote else 0,
                    "layout": layout,
                    **_vote_preview_context(
                        target_type=target_type,
                        target_id=post.id,
                        like_count=post.like_count,
                        dislike_count=post.dislike_count,
                    ),
                },
            )
        from predictions.selectors import get_prediction_with_interactions

        prediction = get_prediction_with_interactions(int(target_id))
        if prediction is None:
            from predictions.models import Prediction

            raise Prediction.DoesNotExist
        user_vote = get_user_vote(request.user, target_type, int(target_id))
        layout = request.POST.get("layout", "vertical")
        if layout == "forecasts":
            return render(
                request,
                "dashboard/partials/forecast_vote_section.html",
                {
                    "prediction": prediction,
                    "prediction_vote": user_vote.value if user_vote else 0,
                    **_vote_preview_context(
                        target_type=target_type,
                        target_id=prediction.id,
                        like_count=prediction.like_count,
                        dislike_count=prediction.dislike_count,
                    ),
                },
            )
        return render(
            request,
            "comments/partials/vote_block.html",
            {
                "target_type": Vote.TargetType.PREDICTION,
                "target_id": prediction.id,
                "score": prediction.popularity_score,
                "user_vote": user_vote.value if user_vote else 0,
                "layout": layout,
                "after_vote_focus": f"prediction-discussion-{prediction.id}",
                **_vote_preview_context(
                    target_type=target_type,
                    target_id=prediction.id,
                    like_count=prediction.like_count,
                    dislike_count=prediction.dislike_count,
                ),
            },
        )

    return safe_redirect_to_referer(request, fallback="/")


def vote_reactions_sheet(request):
    """Instagram-style bottom sheet listing who liked or disliked content."""
    target_type = request.GET.get("target_type")
    target_id = request.GET.get("target_id")
    tab = request.GET.get("tab", "likes")

    if target_type not in (
        Vote.TargetType.COMMENT,
        Vote.TargetType.PREDICTION,
        Vote.TargetType.PULSE_POST,
        Vote.TargetType.PULSE_COMMENT,
    ):
        return HttpResponseBadRequest(_("Invalid target type"))

    try:
        target_id = int(target_id)
    except (TypeError, ValueError):
        return HttpResponseBadRequest(_("Invalid target id"))

    if tab not in ("likes", "dislikes"):
        tab = "likes"

    like_count, dislike_count = get_target_vote_counts(
        target_type=target_type,
        target_id=target_id,
    )
    like_voters = get_target_voters(
        target_type=target_type,
        target_id=target_id,
        value=1,
    )
    dislike_voters = get_target_voters(
        target_type=target_type,
        target_id=target_id,
        value=-1,
    )

    return render(
        request,
        "comments/partials/vote_reactions_sheet.html",
        {
            "target_type": target_type,
            "target_id": target_id,
            "active_tab": tab,
            "like_count": like_count,
            "dislike_count": dislike_count,
            "like_voters": like_voters,
            "dislike_voters": dislike_voters,
        },
    )


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
