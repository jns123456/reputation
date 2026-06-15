"""Prediction serializers and viewsets for API v1."""

from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from api.permissions import HasApiScope, IsReadOnlyOrAuthenticated
from predictions.models import Prediction
from predictions.services import create_prediction, exit_prediction
from reputation.services import calculate_unrealized_reputation


class PredictionSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()
    market_slug = serializers.CharField(source="market.slug", read_only=True)
    live_reputation_pnl = serializers.SerializerMethodField()

    class Meta:
        model = Prediction
        fields = (
            "id",
            "username",
            "market",
            "market_slug",
            "predicted_outcome",
            "predicted_direction",
            "probability_at_prediction_time",
            "probability_at_exit_time",
            "reasoning",
            "status",
            "is_correct",
            "popularity_score",
            "live_reputation_pnl",
            "created_at",
            "resolved_at",
            "exited_at",
        )
        read_only_fields = fields

    def get_username(self, obj):
        return obj.user.username if obj.user.show_username_publicly else None

    def get_live_reputation_pnl(self, obj):
        if obj.status != Prediction.Status.PENDING:
            return None
        return calculate_unrealized_reputation(obj)


class PredictionCreateSerializer(serializers.Serializer):
    market = serializers.SlugRelatedField(
        slug_field="slug",
        queryset=Prediction._meta.get_field("market").related_model.objects.all(),
    )
    predicted_outcome = serializers.CharField(max_length=200)
    predicted_direction = serializers.ChoiceField(
        choices=Prediction.Direction.choices,
        default=Prediction.Direction.YES,
    )
    reasoning = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    dry_run = serializers.BooleanField(default=False, required=False)


class PredictionViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsReadOnlyOrAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return PredictionCreateSerializer
        return PredictionSerializer

    def get_queryset(self):
        qs = Prediction.objects.select_related("user", "market").exclude(
            status=Prediction.Status.VOID
        )
        market_slug = self.request.query_params.get("market")
        username = self.request.query_params.get("user")
        status_filter = self.request.query_params.get("status")
        if market_slug:
            qs = qs.filter(market__slug=market_slug)
        if username:
            qs = qs.filter(user__username=username)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def get_permissions(self):
        if self.action in {"create", "exit"}:
            return [HasApiScope("predictions:write")]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = PredictionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        market = data["market"]
        outcome = data["predicted_outcome"].strip()
        direction = data["predicted_direction"]
        reasoning = data.get("reasoning", "")

        valid_outcomes = [label.lower() for label in market.outcome_labels]
        if valid_outcomes and outcome.lower() not in valid_outcomes:
            return Response(
                {"detail": "predicted_outcome is not valid for this market."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not market.is_forecastable:
            return Response(
                {"detail": "This market is not open for forecasts."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if data.get("dry_run"):
            return Response(
                {
                    "dry_run": True,
                    "would_create": {
                        "market_id": market.id,
                        "market_slug": market.slug,
                        "predicted_outcome": outcome,
                        "predicted_direction": direction,
                    },
                },
                status=status.HTTP_200_OK,
            )

        prediction = create_prediction(
            user=request.user,
            market=market,
            predicted_outcome=outcome,
            predicted_direction=direction,
            reasoning=reasoning,
        )
        return Response(
            PredictionSerializer(prediction).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="exit")
    def exit(self, request, pk=None):
        prediction = self.get_object()
        if prediction.user_id != request.user.id:
            return Response(
                {"detail": "Cannot exit another user's forecast."},
                status=status.HTTP_403_FORBIDDEN,
            )
        prediction = exit_prediction(prediction=prediction, user=request.user)
        return Response(PredictionSerializer(prediction).data)
