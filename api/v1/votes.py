"""Vote API endpoints."""

from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import HasApiScope, scoped_permission
from rest_framework.permissions import IsAuthenticated
from comments.models import Vote
from comments.services import cast_vote, get_user_vote


class VoteSerializer(serializers.Serializer):
    target_type = serializers.ChoiceField(choices=Vote.TargetType.choices)
    target_id = serializers.IntegerField(min_value=1)
    value = serializers.IntegerField()

    def validate_value(self, value):
        if value not in (-1, 0, 1):
            raise serializers.ValidationError("value must be -1, 0, or 1.")
        return value


class VoteView(APIView):
    permission_classes = [scoped_permission("votes:write")]

    def post(self, request):
        serializer = VoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        vote = cast_vote(
            user=request.user,
            target_type=data["target_type"],
            target_id=data["target_id"],
            value=data["value"],
        )
        if vote is None:
            return Response({"removed": True}, status=status.HTTP_200_OK)
        return Response(
            {
                "target_type": vote.target_type,
                "target_id": vote.target_id,
                "value": vote.value,
            },
            status=status.HTTP_200_OK,
        )


class MyVoteView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [IsAuthenticated()]
        return [HasApiScope("votes:write")]

    def get(self, request):
        target_type = request.query_params.get("target_type")
        target_id = request.query_params.get("target_id")
        if not target_type or not target_id:
            return Response(
                {"detail": "target_type and target_id are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            target_id = int(target_id)
        except (TypeError, ValueError):
            return Response(
                {"detail": "target_id must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        vote = get_user_vote(
            user=request.user,
            target_type=target_type,
            target_id=target_id,
        )
        if vote is None:
            return Response({"value": 0})
        return Response({"value": vote.value})
