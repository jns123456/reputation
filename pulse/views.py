from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from accounts.http_utils import safe_redirect_to_referer

from pulse.context import get_forum_page_context
from pulse.forms import CommentForm, PostForm
from pulse.models import Post
from pulse.selectors import (
    build_feed_item,
    build_poll_context,
    build_post_discussion,
    get_post_with_interactions,
)
from pulse.services import (
    create_post,
    create_pulse_comment,
    delete_post,
    delete_pulse_comment,
    toggle_repost,
    vote_on_poll,
)

from accounts import abuse_services
from accounts.write_guard import ContentRejected, write_guard_user_message


@require_GET
def pulse(request):
    context = get_forum_page_context(
        request=request,
        sort=request.GET.get("sort", "recent"),
        page=request.GET.get("page", 1),
    )
    context["post_form"] = PostForm() if request.user.is_authenticated else None
    return render(request, "forum/forum.html", context)


@require_GET
def pulse_feed(request):
    context = get_forum_page_context(
        request=request,
        sort=request.GET.get("sort", "recent"),
        page=request.GET.get("page", 1),
    )
    if context["feed_page"] > 1:
        return render(request, "forum/partials/feed_page.html", context)
    return render(request, "forum/partials/feed.html", context)


@login_required
@require_POST
def create_post_view(request):
    form = PostForm(request.POST, request.FILES)
    if not form.is_valid():
        if request.headers.get("HX-Request"):
            return render(
                request,
                "forum/partials/compose_form.html",
                {"post_form": form},
                status=400,
            )
        return redirect("forum:feed")

    try:
        post = create_post(
            user=request.user,
            body=form.cleaned_data["body"],
            image=form.cleaned_data.get("image"),
            poll_payload=form.cleaned_data.get("poll_payload"),
        )
    except (ValueError, ContentRejected) as exc:
        if request.headers.get("HX-Request"):
            form.add_error(None, write_guard_user_message(exc))
            return render(
                request,
                "forum/partials/compose_form.html",
                {"post_form": form},
                status=400,
            )
        messages.error(request, write_guard_user_message(exc))
        return redirect("forum:feed")
    except abuse_services.RateLimitExceeded as exc:
        if request.headers.get("HX-Request"):
            form.add_error(None, write_guard_user_message(exc))
            return render(
                request,
                "forum/partials/compose_form.html",
                {"post_form": form},
                status=429,
            )
        messages.error(request, write_guard_user_message(exc))
        return redirect("forum:feed")

    if request.headers.get("HX-Request"):
        post = get_post_with_interactions(post.id)
        post.comment_count = 0
        item = build_feed_item(
            post=post,
            user=request.user,
            post_votes={},
            bookmarked_ids=set(),
            repost_counts={},
            user_reposted_ids=set(),
        )
        return render(
            request,
            "forum/partials/post_card_from_item.html",
            {"item": item},
        )

    return redirect("forum:feed")


@require_GET
def post_detail(request, post_id):
    post = get_object_or_404(
        Post.objects.select_related(
            "user",
            "user__profile",
            "reposted_from",
            "reposted_from__user",
            "reposted_from__user__profile",
        ),
        pk=post_id,
    )
    context = build_post_discussion(user=request.user, post=post)
    context["comment_form"] = CommentForm()
    return render(request, "forum/post_detail.html", context)


@login_required
@require_POST
def create_comment_view(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    form = CommentForm(request.POST)
    parent_id = request.POST.get("parent_comment")

    if not form.is_valid():
        return HttpResponseBadRequest(_("Invalid comment"))

    parent = None
    if parent_id:
        parent = post.comments.filter(pk=parent_id).first()

    try:
        create_pulse_comment(
            user=request.user,
            post=post,
            body=form.cleaned_data["body"],
            parent_comment=parent,
        )
    except (ValueError, ContentRejected) as exc:
        return HttpResponseBadRequest(write_guard_user_message(exc))
    except abuse_services.RateLimitExceeded as exc:
        return HttpResponseBadRequest(write_guard_user_message(exc), status=429)

    if request.headers.get("HX-Request"):
        reply_context = request.POST.get("reply_context", "detail")
        context = build_post_discussion(user=request.user, post=post)
        if reply_context == "feed":
            return render(
                request,
                "forum/partials/comment_feed_response.html",
                {
                    "post": context["post"],
                    "original_post": context["original_post"],
                    "comment_count": context["comment_count"],
                    "post_vote": context["post_vote"],
                    "is_bookmarked": context["is_bookmarked"],
                    "repost_count": context["repost_count"],
                    "is_reposted": context["is_reposted"],
                },
            )
        return render(
            request,
            "forum/partials/post_discussion_inner.html",
            context,
        )

    return redirect("forum:detail", post_id=post.id)


@login_required
@require_POST
def delete_comment_view(request, post_id, comment_id):
    post = get_object_or_404(Post, pk=post_id)
    from pulse.models import Comment

    comment = get_object_or_404(Comment, pk=comment_id, post=post)
    try:
        delete_pulse_comment(user=request.user, comment=comment)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))

    if request.headers.get("HX-Request"):
        context = build_post_discussion(user=request.user, post=post)
        return render(
            request,
            "forum/partials/post_discussion_inner.html",
            context,
        )

    return redirect("forum:detail", post_id=post.id)


@login_required
@require_POST
def repost_toggle(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    try:
        result, created = toggle_repost(user=request.user, post=post)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))
    except abuse_services.RateLimitExceeded as exc:
        return HttpResponseBadRequest(write_guard_user_message(exc), status=429)

    original_post = post.original_post
    repost_counts = {
        original_post.id: Post.objects.filter(reposted_from=original_post).count()
    }
    user_reposted_ids = set()
    if Post.objects.filter(user=request.user, reposted_from=original_post).exists():
        user_reposted_ids.add(original_post.id)

    button_context = {
        "post": post,
        "original_post": original_post,
        "repost_count": repost_counts.get(original_post.id, 0),
        "is_reposted": original_post.id in user_reposted_ids,
    }

    if request.headers.get("HX-Request"):
        context = {
            **button_context,
            "repost_created": created,
            "removed_repost_id": result if not created else None,
        }
        if created:
            repost = (
                Post.objects.select_related(
                    "user",
                    "user__profile",
                    "reposted_from",
                    "reposted_from__user",
                    "reposted_from__user__profile",
                )
                .annotate(comment_count=Count("comments", distinct=True))
                .get(pk=result.id)
            )
            context["new_feed_item"] = build_feed_item(
                post=repost,
                user=request.user,
                post_votes={},
                bookmarked_ids=set(),
                repost_counts=repost_counts,
                user_reposted_ids=user_reposted_ids,
            )
        return render(request, "forum/partials/repost_response.html", context)

    return safe_redirect_to_referer(request, fallback=reverse("forum:feed"))


@login_required
@require_POST
def delete_post_view(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    try:
        delete_post(user=request.user, post=post)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))

    if request.headers.get("HX-Request"):
        response = HttpResponse(status=200)
        if request.POST.get("redirect") == "1":
            response["HX-Redirect"] = reverse("forum:feed")
        return response

    return redirect("forum:feed")


@login_required
@require_POST
def poll_vote_view(request, post_id):
    from pulse.models import Poll, PollOption

    post = get_object_or_404(Post, pk=post_id)
    content_post = post.original_post
    poll = get_object_or_404(Poll, post=content_post)
    option_id = request.POST.get("option_id")
    option = get_object_or_404(PollOption, pk=option_id, poll=poll)

    try:
        vote_on_poll(user=request.user, poll=poll, option=option)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))
    except abuse_services.RateLimitExceeded as exc:
        return HttpResponseBadRequest(write_guard_user_message(exc), status=429)

    if request.headers.get("HX-Request"):
        refreshed_post = get_post_with_interactions(content_post.id)
        poll_context = build_poll_context(post=refreshed_post, user=request.user)
        if poll_context is None:
            return HttpResponseBadRequest(_("Poll not found"))
        return render(
            request,
            "forum/partials/post_poll.html",
            {
                "post": refreshed_post,
                **poll_context,
            },
        )

    return redirect("forum:detail", post_id=post.id)
