"""Social graph API: follows, bookmarks, market watch."""

from django.contrib.auth import get_user_model
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.bookmark_services import toggle_bookmark
from accounts.follow_services import toggle_follow, toggle_market_watch, toggle_topic_follow
from accounts.models import Bookmark
from api.permissions import HasApiScope
from markets.models import Market

User = get_user_model()


class FollowUserSerializer(serializers.Serializer):
    username = serializers.CharField()


class FollowUserView(APIView):
    permission_classes = [HasApiScope("social:write")]

    def post(self, request):
        serializer = FollowUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        following = User.objects.filter(username=serializer.validated_data["username"]).first()
        if following is None:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        following_now = toggle_follow(follower=request.user, following_user=following)
        return Response({"following": following_now, "username": following.username})


class FollowTopicSerializer(serializers.Serializer):
    category_slug = serializers.CharField()


class FollowTopicView(APIView):
    permission_classes = [HasApiScope("social:write")]

    def post(self, request):
        serializer = FollowTopicSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        following_now = toggle_topic_follow(
            user=request.user,
            category_slug=serializer.validated_data["category_slug"],
        )
        return Response(
            {
                "following": following_now,
                "category_slug": serializer.validated_data["category_slug"],
            }
        )


class MarketWatchSerializer(serializers.Serializer):
    market = serializers.SlugRelatedField(slug_field="slug", queryset=Market.objects.all())


class MarketWatchView(APIView):
    permission_classes = [HasApiScope("social:write")]

    def post(self, request):
        serializer = MarketWatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        watching_now = toggle_market_watch(
            user=request.user,
            market=serializer.validated_data["market"],
        )
        return Response(
            {
                "watching": watching_now,
                "market_slug": serializer.validated_data["market"].slug,
            }
        )


class BookmarkSerializer(serializers.Serializer):
    target_type = serializers.ChoiceField(choices=Bookmark.TargetType.choices)
    target_id = serializers.IntegerField(min_value=1)


class BookmarkView(APIView):
    permission_classes = [HasApiScope("social:write")]

    def post(self, request):
        serializer = BookmarkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        bookmarked_now = toggle_bookmark(
            user=request.user,
            target_type=data["target_type"],
            target_id=data["target_id"],
        )
        return Response(
            {
                "bookmarked": bookmarked_now,
                "target_type": data["target_type"],
                "target_id": data["target_id"],
            }
        )
