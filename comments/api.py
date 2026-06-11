from rest_framework import serializers, viewsets

from comments.models import Comment


class CommentSerializer(serializers.ModelSerializer):
    # Anonymous identity mode must hide the username (mirrors MCP serializers).
    username = serializers.SerializerMethodField()

    def get_username(self, obj):
        return obj.user.username if obj.user.show_username_publicly else None

    class Meta:
        model = Comment
        fields = (
            "id",
            "username",
            "market",
            "prediction",
            "parent_comment",
            "body",
            "popularity_score",
            "created_at",
        )


class CommentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Comment.objects.select_related("user", "market").all()
    serializer_class = CommentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        market_slug = self.request.query_params.get("market")
        if market_slug:
            qs = qs.filter(market__slug=market_slug)
        return qs
