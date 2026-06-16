"""API v1 URL routing."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api.v1.challenges import ChallengeViewSet
from api.v1.comments import CommentViewSet
from api.v1.forum import PulsePostViewSet
from api.v1.leaderboards import (
    AbsoluteReputationLeaderboardView,
    PopularityLeaderboardView,
    ReputationLeaderboardView,
)
from api.v1.markets import MarketViewSet
from api.v1.predictions import PredictionViewSet
from api.v1.profiles import UserProfileViewSet
from api.v1.reputation import ReputationEventViewSet
from api.v1.rules import AgentParticipationRulesView, ApiDiscoveryView, ReputationRulesView
from api.v1.schema_views import (
    PredictStampSpectacularAPIView,
    PredictStampSpectacularRedocView,
    PredictStampSpectacularSwaggerView,
)
from api.v1.social import (
    BookmarkView,
    FollowTopicView,
    FollowUserView,
    MarketWatchView,
)
from api.v1.votes import MyVoteView, VoteView

router = DefaultRouter()
router.register("markets", MarketViewSet, basename="v1-market")
router.register("predictions", PredictionViewSet, basename="v1-prediction")
router.register("comments", CommentViewSet, basename="v1-comment")
router.register("profiles", UserProfileViewSet, basename="v1-profile")
router.register("forum/posts", PulsePostViewSet, basename="v1-forum-post")
router.register("challenges", ChallengeViewSet, basename="v1-challenge")
router.register("reputation/events", ReputationEventViewSet, basename="v1-reputation-event")

urlpatterns = [
    path("", ApiDiscoveryView.as_view(), name="api-v1-discovery"),
    path("", include(router.urls)),
    path(
        "leaderboards/reputation/",
        ReputationLeaderboardView.as_view(),
        name="v1-leaderboard-reputation",
    ),
    path(
        "leaderboards/reputation/absolute/",
        AbsoluteReputationLeaderboardView.as_view(),
        name="v1-leaderboard-reputation-absolute",
    ),
    path(
        "leaderboards/popularity/",
        PopularityLeaderboardView.as_view(),
        name="v1-leaderboard-popularity",
    ),
    path("rules/reputation/", ReputationRulesView.as_view(), name="v1-rules-reputation"),
    path(
        "rules/agent-participation/",
        AgentParticipationRulesView.as_view(),
        name="v1-rules-agent-participation",
    ),
    path("votes/", VoteView.as_view(), name="v1-vote"),
    path("votes/mine/", MyVoteView.as_view(), name="v1-vote-mine"),
    path("social/follow/", FollowUserView.as_view(), name="v1-social-follow"),
    path("social/follow-topic/", FollowTopicView.as_view(), name="v1-social-follow-topic"),
    path("social/market-watch/", MarketWatchView.as_view(), name="v1-social-market-watch"),
    path("social/bookmark/", BookmarkView.as_view(), name="v1-social-bookmark"),
    path("schema/", PredictStampSpectacularAPIView.as_view(), name="v1-schema"),
    path(
        "schema/swagger-ui/",
        PredictStampSpectacularSwaggerView.as_view(url_name="v1-schema"),
        name="v1-swagger-ui",
    ),
    path(
        "schema/redoc/",
        PredictStampSpectacularRedocView.as_view(url_name="v1-schema"),
        name="v1-redoc",
    ),
]
