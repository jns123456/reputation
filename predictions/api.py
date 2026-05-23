from rest_framework import serializers, viewsets

from predictions.models import Prediction


class PredictionSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Prediction
        fields = (
            "id",
            "username",
            "market",
            "predicted_outcome",
            "confidence",
            "probability_at_prediction_time",
            "reasoning",
            "status",
            "is_correct",
            "popularity_score",
            "created_at",
            "resolved_at",
        )
        read_only_fields = fields


class PredictionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Prediction.objects.select_related("user", "market").exclude(
        status=Prediction.Status.VOID
    )
    serializer_class = PredictionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        market_slug = self.request.query_params.get("market")
        username = self.request.query_params.get("user")
        if market_slug:
            qs = qs.filter(market__slug=market_slug)
        if username:
            qs = qs.filter(user__username=username)
        return qs
