from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from pulse.context import get_forum_page_context
from pulse.forms import CommentForm, PostForm
from pulse.models import Post
from pulse.selectors import build_feed_item, build_post_discussion
from pulse.services import create_post, create_pulse_comment, toggle_repost


@require_GET
def pulse(request):
    context = get_forum_page_context(request=request)
    context["post_form"] = PostForm() if request.user.is_authenticated else None
    return render(request, "forum/forum.html", context)


@require_GET
def pulse_feed(request):
    context = get_forum_page_context(request=request)
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

    post = create_post(
        user=request.user,
        body=form.cleaned_data["body"],
        image=form.cleaned_data.get("image"),
    )

    if request.headers.get("HX-Request"):
        post = Post.objects.select_related(
            "user",
            "user__profile",
            "reposted_from",
            "reposted_from__user",
            "reposted_from__user__profile",
        ).get(pk=post.id)
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
            "forum/partials/post_card.html",
            item,
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
        return HttpResponseBadRequest("Invalid comment")

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

    return redirect(request.META.get("HTTP_REFERER", "/forum/"))
