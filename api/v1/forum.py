"""Forum (Pulse) API endpoints."""

from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from api.permissions import HasApiScope, IsReadOnlyOrAuthenticated
from pulse.models import Post
from pulse.selectors import get_pulse_posts
from pulse.services import create_post, create_pulse_comment, toggle_repost, vote_on_poll


class PulsePostSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            "id",
            "username",
            "body",
            "audience",
            "popularity_score",
            "reposted_from",
            "created_at",
        )
        read_only_fields = fields

    def get_username(self, obj):
        return obj.user.username if obj.user.show_username_publicly else None


class PulsePostCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=200, required=False, allow_blank=True)
    poll_options = serializers.ListField(
        child=serializers.CharField(max_length=80),
        required=False,
        allow_empty=False,
        max_length=4,
    )
    poll_duration_days = serializers.IntegerField(min_value=1, max_value=7, required=False)
    dry_run = serializers.BooleanField(default=False, required=False)


class PulseCommentCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=500)
    parent_comment_id = serializers.IntegerField(required=False, allow_null=True)


class PulsePollVoteSerializer(serializers.Serializer):
    option_id = serializers.IntegerField(min_value=1)


class PulsePostViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsReadOnlyOrAuthenticated]
    lookup_value_regex = "[0-9]+"

    def get_serializer_class(self):
        if self.action == "create":
            return PulsePostCreateSerializer
        return PulsePostSerializer

    def get_queryset(self):
        sort = self.request.query_params.get("sort", "recent")
        following_ids = None
        user = self.request.user
        if sort == "following" and user.is_authenticated:
            from accounts.models import UserFollow

            following_ids = list(
                UserFollow.objects.filter(follower=user).values_list("following_id", flat=True)
            )
        posts = get_pulse_posts(sort=sort, limit=50, following_ids=following_ids)
        if not posts:
            return Post.objects.none()
        return Post.objects.filter(pk__in=[p.pk for p in posts]).order_by("-created_at")

    def get_permissions(self):
        if self.action in {"create", "comment", "repost", "poll_vote"}:
            return [HasApiScope("forum:write")]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = PulsePostCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        body = (data.get("body") or "").strip()
        poll_payload = None
        poll_options = data.get("poll_options")
        if poll_options:
            poll_payload = {
                "options": poll_options,
                "duration_days": data.get("poll_duration_days") or 3,
            }
        if not body and not poll_payload:
            return Response(
                {"detail": "body or poll_options is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if data.get("dry_run"):
            return Response(
                {"dry_run": True, "would_create": {"body_length": len(body)}},
                status=status.HTTP_200_OK,
            )
        post = create_post(user=request.user, body=body, poll_payload=poll_payload)
        return Response(PulsePostSerializer(post).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def comment(self, request, pk=None):
        post = self.get_object()
        serializer = PulseCommentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        parent = None
        parent_id = data.get("parent_comment_id")
        if parent_id:
            from pulse.models import Comment as PulseComment

            parent = PulseComment.objects.filter(pk=parent_id, post=post).first()
            if parent is None:
                return Response(
                    {"detail": "parent_comment_id not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        comment = create_pulse_comment(
            user=request.user,
            post=post,
            body=data["body"],
            parent_comment=parent,
        )
        return Response(
            {
                "id": comment.id,
                "body": comment.body,
                "parent_comment": comment.parent_comment_id,
                "created_at": comment.created_at,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def repost(self, request, pk=None):
        post = self.get_object()
        reposted_now = toggle_repost(user=request.user, post=post)
        return Response({"reposted": reposted_now})

    @action(detail=True, methods=["post"], url_path="poll-vote")
    def poll_vote(self, request, pk=None):
        post = self.get_object()
        serializer = PulsePollVoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from pulse.models import Poll, PollOption

        poll = Poll.objects.filter(post=post).first()
        if poll is None:
            return Response({"detail": "Post has no poll."}, status=status.HTTP_400_BAD_REQUEST)
        option = PollOption.objects.filter(
            pk=serializer.validated_data["option_id"],
            poll=poll,
        ).first()
        if option is None:
            return Response({"detail": "Invalid poll option."}, status=status.HTTP_400_BAD_REQUEST)
        vote_on_poll(user=request.user, poll=poll, option=option)
        return Response({"voted": True})
