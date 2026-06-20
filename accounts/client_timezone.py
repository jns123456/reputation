"""Resolve a client IANA timezone from CDN headers, GeoIP, or country fallback."""

from __future__ import annotations

import logging
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.utils import timezone

from accounts.country_language import get_client_ip, get_country_code_from_request

logger = logging.getLogger(__name__)

# Primary zone when only the country is known (multi-zone countries use a sensible default).
COUNTRY_PRIMARY_TIMEZONE: dict[str, str] = {
    "AR": "America/Argentina/Buenos_Aires",
    "AU": "Australia/Sydney",
    "BO": "America/La_Paz",
    "BR": "America/Sao_Paulo",
    "CA": "America/Toronto",
    "CL": "America/Santiago",
    "CN": "Asia/Shanghai",
    "CO": "America/Bogota",
    "CR": "America/Costa_Rica",
    "CU": "America/Havana",
    "DE": "Europe/Berlin",
    "DO": "America/Santo_Domingo",
    "EC": "America/Guayaquil",
    "ES": "Europe/Madrid",
    "FR": "Europe/Paris",
    "GB": "Europe/London",
    "GQ": "Africa/Malabo",
    "GT": "America/Guatemala",
    "HN": "America/Tegucigalpa",
    "IN": "Asia/Kolkata",
    "IT": "Europe/Rome",
    "JP": "Asia/Tokyo",
    "MX": "America/Mexico_City",
    "NI": "America/Managua",
    "PA": "America/Panama",
    "PE": "America/Lima",
    "PR": "America/Puerto_Rico",
    "PT": "Europe/Lisbon",
    "PY": "America/Asuncion",
    "SV": "America/El_Salvador",
    "US": "America/New_York",
    "UY": "America/Montevideo",
    "VE": "America/Caracas",
}


def get_client_timezone_name(request) -> str:
    """
    Best-effort IANA timezone for the client.

    1. CDN/proxy headers (CloudFront viewer timezone)
    2. Optional GeoLite2-City database (GEOIP_CITY_PATH)
    3. Country → primary timezone (from CDN country headers or GeoLite2-Country)
    4. Django ``TIME_ZONE`` (UTC in production)
    """
    for header in ("HTTP_CLOUDFRONT_VIEWER_TIME_ZONE",):
        candidate = (request.META.get(header) or "").strip()
        if _is_valid_timezone(candidate):
            return candidate

    ip = get_client_ip(request)
    if ip:
        city_tz = _lookup_timezone_geoip_city(ip)
        if city_tz:
            return city_tz

        if getattr(settings, "GEOIP_HTTP_FALLBACK_ENABLED", True):
            from accounts.ip_geo_lookup import lookup_ip_geo

            geo = lookup_ip_geo(ip)
            if geo.timezone_name and _is_valid_timezone(geo.timezone_name):
                return geo.timezone_name
            if geo.country_code:
                country_tz = COUNTRY_PRIMARY_TIMEZONE.get(geo.country_code.upper())
                if country_tz and _is_valid_timezone(country_tz):
                    return country_tz

    country = get_country_code_from_request(request)
    if country:
        country_tz = COUNTRY_PRIMARY_TIMEZONE.get(country.upper())
        if country_tz and _is_valid_timezone(country_tz):
            return country_tz

    return settings.TIME_ZONE


def timezone_display_label(tz_name: str, at: datetime | None = None) -> str:
    """Short label for UI (e.g. ART, CEST, UTC)."""
    at = at or timezone.now()
    try:
        localized = at.astimezone(ZoneInfo(tz_name))
    except ZoneInfoNotFoundError:
        return "UTC"
    label = localized.tzname() or localized.strftime("%Z")
    return label or tz_name


def _is_valid_timezone(name: str) -> bool:
    if not name:
        return False
    try:
        ZoneInfo(name)
        return True
    except ZoneInfoNotFoundError:
        return False


@lru_cache(maxsize=1)
def _geoip_city_reader():
    path = getattr(settings, "GEOIP_CITY_PATH", "") or ""
    if not path:
        return None
    db_path = Path(path)
    if not db_path.is_file():
        logger.warning("GEOIP_CITY_PATH does not exist: %s", db_path)
        return None
    try:
        from geoip2.database import Reader
    except ImportError:
        logger.warning("geoip2 is not installed; pip install geoip2 for IP timezone lookup")
        return None
    return Reader(str(db_path))


def _lookup_timezone_geoip_city(ip: str) -> str | None:
    if ip in {"127.0.0.1", "::1"}:
        return None
    reader = _geoip_city_reader()
    if reader is None:
        return None
    try:
        response = reader.city(ip)
        tz_name = (response.location.time_zone or "").strip()
        if tz_name and _is_valid_timezone(tz_name):
            return tz_name
    except Exception:
        logger.debug("GeoIP city timezone lookup failed for %s", ip, exc_info=True)
    return None
