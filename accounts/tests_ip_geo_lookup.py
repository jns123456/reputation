"""Tests for cached HTTP IP geolocation fallback."""

from unittest.mock import patch

from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings

from accounts.client_timezone import get_client_timezone_name
from accounts.country_language import get_country_code_from_request
from accounts.ip_geo_lookup import IpGeoResult, lookup_ip_geo


@override_settings(GEOIP_HTTP_FALLBACK_ENABLED=True)
class IpGeoHttpFallbackTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_lookup_ip_geo_uses_cache(self):
        with patch("accounts.ip_geo_lookup._fetch_ip_geo") as fetch:
            fetch.return_value = IpGeoResult(country_code="UY", timezone_name="America/Montevideo")
            first = lookup_ip_geo("181.0.0.1")
            second = lookup_ip_geo("181.0.0.1")
        self.assertEqual(first.timezone_name, "America/Montevideo")
        self.assertEqual(second.timezone_name, "America/Montevideo")
        fetch.assert_called_once()

    def test_client_timezone_from_http_lookup(self):
        request = RequestFactory().get("/")
        request.META["REMOTE_ADDR"] = "181.0.0.1"
        with patch(
            "accounts.ip_geo_lookup._fetch_ip_geo",
            return_value=IpGeoResult(country_code="UY", timezone_name="America/Montevideo"),
        ):
            self.assertEqual(get_client_timezone_name(request), "America/Montevideo")

    def test_country_from_http_lookup(self):
        request = RequestFactory().get("/")
        request.META["REMOTE_ADDR"] = "181.0.0.1"
        with patch(
            "accounts.ip_geo_lookup._fetch_ip_geo",
            return_value=IpGeoResult(country_code="UY", timezone_name="America/Montevideo"),
        ):
            self.assertEqual(get_country_code_from_request(request), "UY")

    @override_settings(GEOIP_HTTP_FALLBACK_ENABLED=False)
    def test_http_fallback_can_be_disabled(self):
        request = RequestFactory().get("/")
        request.META["REMOTE_ADDR"] = "181.0.0.1"
        with patch("accounts.ip_geo_lookup._fetch_ip_geo") as fetch:
            self.assertEqual(get_client_timezone_name(request), "UTC")
            fetch.assert_not_called()
