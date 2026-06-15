"""User-facing API documentation views."""

from django.conf import settings
from django.shortcuts import render
from django.urls import reverse

from accounts.agent_services import READ_SCOPES, WRITE_SCOPES
from api.docs_catalog import ENDPOINT_SECTIONS, SCOPES


def api_docs(request):
    base_url = request.build_absolute_uri("/").rstrip("/")
    example_token = "mcp_abcd1234_your_secret_here"
    context = {
        "base_url": base_url,
        "sections": ENDPOINT_SECTIONS,
        "scopes": SCOPES,
        "read_scopes": READ_SCOPES,
        "write_scopes": WRITE_SCOPES,
        "writes_enabled": getattr(settings, "API_WRITES_ENABLED", True),
        "swagger_url": reverse("v1-swagger-ui"),
        "redoc_url": reverse("v1-redoc"),
        "schema_url": reverse("v1-schema"),
        "discovery_url": reverse("api-v1-discovery"),
        "tokens_url": reverse("mcp:developer_settings"),
        "example_curl_markets": (
            f'curl -H "Authorization: Bearer {example_token}" '
            f'"{base_url}/api/v1/markets/?forecastable=1"'
        ),
        "example_curl_forecast": (
            f'curl -X POST -H "Authorization: Bearer {example_token}" '
            f'-H "Content-Type: application/json" '
            f'-d \'{{"market":"your-market-slug","predicted_outcome":"Yes",'
            f'"predicted_direction":"yes","reasoning":"API test"}}\' '
            f'"{base_url}/api/v1/predictions/"'
        ),
    }
    return render(request, "api/docs.html", context)
