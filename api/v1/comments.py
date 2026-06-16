"""Comment serializers and viewsets for API v1."""

from rest_framework import mixins, serializers, status, viewsets
from rest_framework.response import Response

from api.permissions import HasApiScope, IsReadOnlyOrAuthenticated
from comments.models import Comment
from comments.services import create_comment


class CommentSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()
    market_slug = serializers.CharField(source="market.slug", read_only=True)

    class Meta:
        model = Comment
        fields = (
            "id",
            "username",
            "market",
            "market_slug",
            "prediction",
            "parent_comment",
            "body",
            "popularity_score",
            "created_at",
        )
        read_only_fields = fields

    def get_username(self, obj):
        return obj.user.username if obj.user.show_username_publicly else None


class CommentCreateSerializer(serializers.Serializer):
    market = serializers.SlugRelatedField(
        slug_field="slug",
        queryset=Comment._meta.get_field("market").related_model.objects.all(),
    )
    body = serializers.CharField(max_length=5000)
    parent_comment_id = serializers.IntegerField(required=False, allow_null=True)
    prediction_id = serializers.IntegerField(required=False, allow_null=True)
    dry_run = serializers.BooleanField(default=False, required=False)


class CommentViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsReadOnlyOrAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return CommentCreateSerializer
        return CommentSerializer

    def get_queryset(self):
        qs = Comment.objects.select_related("user", "market").all()
        market_slug = self.request.query_params.get("market")
        prediction_id = self.request.query_params.get("prediction")
        if market_slug:
            qs = qs.filter(market__slug=market_slug)
        if prediction_id:
            qs = qs.filter(prediction_id=prediction_id)
        return qs

    def get_permissions(self):
        if self.action == "create":
            return [HasApiScope("comments:write")()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = CommentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        market = data["market"]
        body = data["body"].strip()
        if not body:
            return Response({"detail": "body is required."}, status=status.HTTP_400_BAD_REQUEST)

        parent_comment = None
        parent_id = data.get("parent_comment_id")
        if parent_id:
            parent_comment = Comment.objects.filter(pk=parent_id).first()
            if parent_comment is None:
                return Response(
                    {"detail": "parent_comment_id not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        prediction = None
        prediction_id = data.get("prediction_id")
        if prediction_id:
            from predictions.models import Prediction

            prediction = Prediction.objects.filter(pk=prediction_id).first()
            if prediction is None:
                return Response(
                    {"detail": "prediction_id not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        if data.get("dry_run"):
            return Response(
                {
                    "dry_run": True,
                    "would_create": {"market_id": market.id, "body_length": len(body)},
                },
                status=status.HTTP_200_OK,
            )

        comment = create_comment(
            user=request.user,
            market=market,
            body=body,
            parent_comment=parent_comment,
            prediction=prediction,
        )
        return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)
