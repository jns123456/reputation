"""Challenge API endpoints."""

from django.contrib.auth import get_user_model
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from api.permissions import HasApiScope, IsReadOnlyOrAuthenticated
from challenges.models import Challenge
from challenges.selectors import (
    get_challenge_for_spectator,
    get_challenge_for_user,
    get_challenge_standings,
    get_user_challenges,
)
from challenges.services import (
    accept_challenge,
    cancel_challenge,
    create_challenge,
    decline_challenge,
)

User = get_user_model()


def _serialize_standings(standings):
    return [
        {
            "rank": row["rank"],
            "username": (
                row["participant"].user.username
                if row["participant"].user.show_username_publicly
                else None
            ),
            "display_name": row["participant"].user.public_name,
            "realized_points": row["realized_points"],
            "unrealized_points": row["unrealized_points"],
            "total_points": row["total_points"],
        }
        for row in standings
    ]


class ChallengeSerializer(serializers.ModelSerializer):
    creator_username = serializers.SerializerMethodField()
    display_title = serializers.SerializerMethodField()
    market_ids = serializers.SerializerMethodField()
    participant_count = serializers.SerializerMethodField()

    class Meta:
        model = Challenge
        fields = (
            "id",
            "title",
            "display_title",
            "status",
            "creator_username",
            "winner",
            "market_ids",
            "participant_count",
            "started_at",
            "completed_at",
            "created_at",
        )
        read_only_fields = fields

    def get_creator_username(self, obj):
        return obj.creator.username if obj.creator.show_username_publicly else None

    def get_display_title(self, obj):
        return obj.display_title

    def get_market_ids(self, obj):
        return list(obj.challenge_markets.values_list("market_id", flat=True))

    def get_participant_count(self, obj):
        return obj.participants.count()


class ChallengeCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    market_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=10,
    )
    opponent_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
    )
    dry_run = serializers.BooleanField(default=False, required=False)


class ChallengeViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsReadOnlyOrAuthenticated]
    lookup_value_regex = "[0-9]+"

    def get_serializer_class(self):
        if self.action == "create":
            return ChallengeCreateSerializer
        return ChallengeSerializer

    def get_queryset(self):
        user = self.request.user if self.request.user.is_authenticated else None
        if user is None:
            return Challenge.objects.none()
        qs = get_user_challenges(user)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def get_object(self):
        pk = self.kwargs["pk"]
        user = self.request.user
        if user.is_authenticated:
            challenge = get_challenge_for_user(challenge_id=pk, user=user)
            if challenge is not None:
                return challenge
        challenge = get_challenge_for_spectator(pk)
        if challenge is None:
            raise NotFound("Challenge not found.")
        return challenge

    def get_permissions(self):
        if self.action in {"create", "accept", "decline", "cancel"}:
            return [HasApiScope("challenges:write")()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = ChallengeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data.get("dry_run"):
            return Response(
                {
                    "dry_run": True,
                    "would_create": {
                        "market_ids": data["market_ids"],
                        "opponent_ids": data["opponent_ids"],
                    },
                },
                status=status.HTTP_200_OK,
            )
        challenge = create_challenge(
            creator=request.user,
            title=data.get("title", ""),
            market_ids=data["market_ids"],
            opponent_ids=data["opponent_ids"],
        )
        return Response(ChallengeSerializer(challenge).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def standings(self, request, pk=None):
        challenge = self.get_object()
        return Response(_serialize_standings(get_challenge_standings(challenge)))

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        challenge = self.get_object()
        accept_challenge(challenge=challenge, user=request.user)
        challenge.refresh_from_db()
        return Response(ChallengeSerializer(challenge).data)

    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        challenge = self.get_object()
        decline_challenge(challenge=challenge, user=request.user)
        challenge.refresh_from_db()
        return Response(ChallengeSerializer(challenge).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        challenge = self.get_object()
        cancel_challenge(challenge=challenge, user=request.user)
        challenge.refresh_from_db()
        return Response(ChallengeSerializer(challenge).data)
