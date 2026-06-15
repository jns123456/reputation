"""User profile serializers and viewsets for API v1."""

from rest_framework import serializers, viewsets
from rest_framework.response import Response

from accounts.models import UserProfile
from accounts.selectors import get_top_popular_users, get_top_predictors
from api.permissions import IsReadOnlyOrAuthenticated
from mcp.serializers import serialize_public_profile


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()
    display_name = serializers.CharField(source="user.public_name", read_only=True)
    account_type = serializers.CharField(source="user.account_type", read_only=True)
    is_ai_agent = serializers.BooleanField(source="user.is_ai_agent", read_only=True)
    is_verified = serializers.BooleanField(source="user.is_verified", read_only=True)
    scored_forecast_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = UserProfile
        fields = (
            "username",
            "display_name",
            "account_type",
            "is_ai_agent",
            "is_verified",
            "popularity_points",
            "reputation_points",
            "prediction_count",
            "correct_prediction_count",
            "incorrect_prediction_count",
            "neutral_prediction_count",
            "reputation_score",
            "popularity_score",
            "scored_forecast_count",
        )

    def get_username(self, obj):
        return obj.user.username if obj.user.show_username_publicly else None


class UserProfileViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UserProfile.objects.select_related("user").all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsReadOnlyOrAuthenticated]
    lookup_field = "user__username"
    lookup_value_regex = "[^/]+"

    def get_queryset(self):
        qs = super().get_queryset()
        ranking = self.request.query_params.get("ranking")
        if ranking == "reputation":
            mode = self.request.query_params.get("mode")
            return get_top_predictors(100, mode=mode)
        if ranking == "popularity":
            return get_top_popular_users(100)
        username = self.request.query_params.get("username")
        if username:
            return qs.filter(user__username=username)
        return qs

    def retrieve(self, request, *args, **kwargs):
        profile = self.get_object()
        return Response(serialize_public_profile(profile))
