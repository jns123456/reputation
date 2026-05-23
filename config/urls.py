from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("dashboard.urls")),
    path("accounts/", include("accounts.urls")),
    path("markets/", include("markets.urls")),
    path("predictions/", include("predictions.urls")),
    path("comments/", include("comments.urls")),
    path("challenges/", include("challenges.urls")),
    path("api/", include("config.api_urls")),
]
