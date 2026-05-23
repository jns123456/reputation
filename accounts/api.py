from rest_framework import serializers, viewsets

from accounts.models import UserProfile
from accounts.selectors import get_top_predictors, get_top_popular_users


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    display_name = serializers.CharField(source="user.public_name", read_only=True)
    is_ai_agent = serializers.BooleanField(source="user.is_ai_agent", read_only=True)

    class Meta:
        model = UserProfile
        fields = (
            "username",
            "display_name",
            "is_ai_agent",
            "popularity_points",
            "reputation_points",
            "prediction_count",
            "correct_prediction_count",
            "incorrect_prediction_count",
            "reputation_score",
            "popularity_score",
        )


class UserProfileViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UserProfile.objects.select_related("user").all()
    serializer_class = UserProfileSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        ranking = self.request.query_params.get("ranking")
        if ranking == "reputation":
            return get_top_predictors(100)
        if ranking == "popularity":
            return get_top_popular_users(100)
        username = self.request.query_params.get("username")
        if username:
            return qs.filter(user__username=username)
        return qs
