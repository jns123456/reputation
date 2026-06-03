from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.i18n import set_language

from config import landing_video, pwa_views

urlpatterns = [
    path(
        "assets/landing-hero.mp4",
        landing_video.serve_landing_hero_video,
        name="landing_hero_video",
    ),
    path("i18n/setlang/", set_language, name="set_language"),
    path("sw.js", pwa_views.service_worker, name="service_worker"),
    path("manifest.webmanifest", pwa_views.webmanifest, name="webmanifest"),
    path("admin/", admin.site.urls),
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
