from django.urls import include, path
from rest_framework.routers import DefaultRouter

from accounts.api import UserProfileViewSet
from comments.api import CommentViewSet
from markets.api import MarketViewSet
from predictions.api import PredictionViewSet

router = DefaultRouter()
router.register("markets", MarketViewSet, basename="market")
router.register("predictions", PredictionViewSet, basename="prediction")
router.register("comments", CommentViewSet, basename="comment")
router.register("profiles", UserProfileViewSet, basename="profile")

urlpatterns = [
    path("", include(router.urls)),
]
