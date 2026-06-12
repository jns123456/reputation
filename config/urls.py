from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.i18n import set_language

from config import brand_views, health_views, landing_video, pwa_views
from predictions import views as prediction_card_views

urlpatterns = [
    # Short, public, shareable forecast-card permalinks (no auth required).
    path(
        "p/<int:prediction_id>/",
        prediction_card_views.prediction_detail,
        name="prediction_card",
    ),
    path(
        "p/<int:prediction_id>/og.png",
        prediction_card_views.prediction_og_image,
        name="prediction_card_og",
    ),
    path(
        "p/<int:prediction_id>/share/",
        prediction_card_views.prediction_share,
        name="prediction_card_share",
    ),
    path("health/", health_views.health, name="health"),
    path(
        "brand/auth0-logo.jpg",
        brand_views.serve_auth0_logo,
        name="auth0_logo",
    ),
    path(
        "assets/landing-hero.mp4",
        landing_video.serve_landing_hero_video,
        name="landing_hero_video",
    ),
    path("i18n/setlang/", set_language, name="set_language"),
    path("sw.js", pwa_views.service_worker, name="service_worker"),
    path("manifest.webmanifest", pwa_views.webmanifest, name="webmanifest"),
    path(settings.ADMIN_URL_PATH, admin.site.urls),
    path("", include("dashboard.urls")),
    path("accounts/", include("accounts.urls")),
    path("markets/", include("markets.urls")),
    path("predictions/", include("predictions.urls")),
    path("comments/", include("comments.urls")),
    path("challenges/", include("challenges.urls")),
    path("forum/", include("pulse.urls")),
    path("proof/", include("integrations.urls")),
    path("api/", include("config.api_urls")),
    path("mcp/", include("mcp.urls")),
]

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
