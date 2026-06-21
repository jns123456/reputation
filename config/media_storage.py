"""S3-compatible media storage settings (AWS S3 or Cloudflare R2)."""

from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured


def is_r2_endpoint(endpoint_url: str) -> bool:
    return "r2.cloudflarestorage.com" in (endpoint_url or "")


def resolve_s3_media_settings(
    *,
    bucket_name: str,
    endpoint_url: str = "",
    region_name: str = "",
    custom_domain: str = "",
    default_acl: str | None = None,
    running_tests: bool = False,
) -> dict:
    """Build django-storages settings for pulse forum image uploads."""
    endpoint_url = (endpoint_url or "").strip()
    is_r2 = is_r2_endpoint(endpoint_url)
    resolved_region = (region_name or "").strip() or ("auto" if is_r2 else "us-east-1")
    resolved_domain = (custom_domain or "").strip()
    if not resolved_domain:
        if is_r2:
            if not running_tests:
                raise ImproperlyConfigured(
                    "AWS_S3_CUSTOM_DOMAIN is required for Cloudflare R2 "
                    "(public r2.dev hostname or custom domain, without https://)."
                )
            resolved_domain = "media.example.test"
        else:
            resolved_domain = f"{bucket_name}.s3.{resolved_region}.amazonaws.com"

    settings: dict = {
        "AWS_STORAGE_BUCKET_NAME": bucket_name,
        "AWS_S3_REGION_NAME": resolved_region,
        "AWS_S3_CUSTOM_DOMAIN": resolved_domain,
        "AWS_S3_OBJECT_PARAMETERS": {"CacheControl": "max-age=86400"},
        "AWS_QUERYSTRING_AUTH": False,
        "AWS_S3_FILE_OVERWRITE": False,
        "MEDIA_URL": f"https://{resolved_domain}/",
    }
    if endpoint_url:
        settings["AWS_S3_ENDPOINT_URL"] = endpoint_url

    if is_r2:
        settings["AWS_DEFAULT_ACL"] = None
    elif default_acl is not None and str(default_acl).lower() not in {"", "none", "null"}:
        settings["AWS_DEFAULT_ACL"] = default_acl
    else:
        settings["AWS_DEFAULT_ACL"] = "public-read"

    return settings
