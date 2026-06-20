"""Cached IP → country/timezone lookup when local GeoLite2 databases are unavailable."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

_PRIVATE_IPS = frozenset({"127.0.0.1", "::1"})
_CACHE_TTL_SECONDS = 60 * 60 * 24
_CACHE_PREFIX = "ipgeo:v1:"


@dataclass(frozen=True)
class IpGeoResult:
    country_code: str | None = None
    timezone_name: str | None = None


def lookup_ip_geo(ip: str) -> IpGeoResult:
    """Resolve country and IANA timezone for a public IP via ipwho.is (cached)."""
    if not ip or ip in _PRIVATE_IPS:
        return IpGeoResult()
    if not getattr(settings, "GEOIP_HTTP_FALLBACK_ENABLED", True):
        return IpGeoResult()

    cache_key = f"{_CACHE_PREFIX}{ip}"
    cached = cache.get(cache_key)
    if cached is not None:
        return IpGeoResult(
            country_code=cached.get("country_code"),
            timezone_name=cached.get("timezone_name"),
        )

    result = _fetch_ip_geo(ip)
    cache.set(
        cache_key,
        {
            "country_code": result.country_code,
            "timezone_name": result.timezone_name,
        },
        _CACHE_TTL_SECONDS,
    )
    return result


def _fetch_ip_geo(ip: str) -> IpGeoResult:
    try:
        response = requests.get(f"https://ipwho.is/{ip}", timeout=2.0)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        logger.debug("HTTP IP geo lookup failed for %s", ip, exc_info=True)
        return IpGeoResult()

    if not payload.get("success"):
        return IpGeoResult()

    timezone = payload.get("timezone")
    timezone_name = None
    if isinstance(timezone, dict):
        timezone_name = (timezone.get("id") or "").strip() or None
    elif isinstance(timezone, str):
        timezone_name = timezone.strip() or None

    country_code = (payload.get("country_code") or "").strip().upper() or None
    return IpGeoResult(country_code=country_code, timezone_name=timezone_name)
