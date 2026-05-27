from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.i18n import set_language

urlpatterns = [
    path("i18n/setlang/", set_language, name="set_language"),
    path("admin/", admin.site.urls),
    path("", include("dashboard.urls")),
    path("accounts/", include("accounts.urls")),
    path("markets/", include("markets.urls")),
    path("predictions/", include("predictions.urls")),
    path("comments/", include("comments.urls")),
    path("challenges/", include("challenges.urls")),
    path("forum/", include("pulse.urls")),
    path("api/", include("config.api_urls")),
]

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
