"""Reputation audit trail API."""

from rest_framework import serializers, viewsets

from api.permissions import IsReadOnlyOrAuthenticated
from reputation.models import ReputationEvent


class ReputationEventSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()
    prediction_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = ReputationEvent
        fields = (
            "id",
            "username",
            "prediction_id",
            "event_type",
            "points_delta",
            "reason",
            "created_at",
        )
        read_only_fields = fields

    def get_username(self, obj):
        return obj.user.username if obj.user.show_username_publicly else None


class ReputationEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ReputationEventSerializer
    permission_classes = [IsReadOnlyOrAuthenticated]

    def get_queryset(self):
        qs = ReputationEvent.objects.select_related("user", "prediction").all()
        username = self.request.query_params.get("user")
        prediction_id = self.request.query_params.get("prediction")
        if username:
            qs = qs.filter(user__username=username)
        if prediction_id:
            qs = qs.filter(prediction_id=prediction_id)
        return qs
