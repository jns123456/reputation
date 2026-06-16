"""OpenAPI schema endpoints — public in DEBUG, staff-only in production."""

from django.conf import settings
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.permissions import AllowAny, IsAdminUser


def _openapi_staff_only() -> bool:
    return getattr(settings, "API_OPENAPI_STAFF_ONLY", False)


class _StaffGatedOpenApiMixin:
    def get_permissions(self):
        if _openapi_staff_only():
            return [IsAdminUser()]
        return [AllowAny()]


class PredictStampSpectacularAPIView(_StaffGatedOpenApiMixin, SpectacularAPIView):
    pass


class PredictStampSpectacularSwaggerView(_StaffGatedOpenApiMixin, SpectacularSwaggerView):
    pass


class PredictStampSpectacularRedocView(_StaffGatedOpenApiMixin, SpectacularRedocView):
    pass
