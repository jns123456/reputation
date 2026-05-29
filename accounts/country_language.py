"""Map client country (from IP / proxy headers) to a supported site language."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

# ISO 3166-1 alpha-2 — countries where Spanish is an official language.
SPANISH_OFFICIAL_COUNTRIES = frozenset(
    {
        "AR",
        "BO",
        "CL",
        "CO",
        "CR",
        "CU",
        "DO",
        "EC",
        "ES",
        "GQ",
        "GT",
        "HN",
        "MX",
        "NI",
        "PA",
        "PE",
        "PR",
        "PY",
        "SV",
        "UY",
        "VE",
    }
)

def _supported_languages():
    return frozenset(code for code, _ in settings.LANGUAGES)


def get_client_ip(request) -> str | None:
    """Best-effort client IP behind a reverse proxy."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
        if ip:
            return ip
    ip = request.META.get("REMOTE_ADDR", "").strip()
    return ip or None


def get_country_code_from_request(request) -> str | None:
    """
    Resolve ISO country code for the client.

    1. CDN/proxy headers (Cloudflare, CloudFront)
    2. Optional local GeoLite2-Country database (GEOIP_COUNTRY_PATH)
    """
    for header in ("HTTP_CF_IPCOUNTRY", "HTTP_CLOUDFRONT_VIEWER_COUNTRY"):
        code = (request.META.get(header) or "").strip().upper()
        if len(code) == 2 and code not in {"XX", "T1"}:
            return code

    ip = get_client_ip(request)
    if not ip:
        return None
    return _lookup_country_geoip(ip)


def official_language_for_country(country_code: str | None) -> str | None:
    """Official language mapped to a supported locale (en/es only)."""
    if not country_code or len(country_code) != 2:
        return None
    code = country_code.upper()
    if code in SPANISH_OFFICIAL_COUNTRIES:
        return "es"
    return "en"


def language_for_request_country(request) -> str | None:
    country = get_country_code_from_request(request)
    language = official_language_for_country(country)
    if language and language in _supported_languages():
        return language
    return None


@lru_cache(maxsize=1)
def _geoip_reader():
    path = getattr(settings, "GEOIP_COUNTRY_PATH", "") or ""
    if not path:
        return None
    db_path = Path(path)
    if not db_path.is_file():
        logger.warning("GEOIP_COUNTRY_PATH does not exist: %s", db_path)
        return None
    try:
        from geoip2.database import Reader
    except ImportError:
        logger.warning("geoip2 is not installed; pip install geoip2 for IP country lookup")
        return None
    return Reader(str(db_path))


def _lookup_country_geoip(ip: str) -> str | None:
    if ip in {"127.0.0.1", "::1"}:
        return None
    reader = _geoip_reader()
    if reader is None:
        return None
    try:
        response = reader.country(ip)
        return (response.country.iso_code or "").upper() or None
    except Exception:
        logger.debug("GeoIP lookup failed for %s", ip, exc_info=True)
        return None
