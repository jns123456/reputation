"""Tests for IP / CDN → client timezone resolution and rendering."""

from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.client_timezone import (
    get_client_timezone_name,
    timezone_display_label,
)
from accounts.middleware import ClientTimezoneMiddleware
from integrations.polymarket.soccer_matches import normalize_world_cup_match_event
from integrations.services import import_market_from_normalized
from integrations.tests_soccer_matches import MEXICO_VS_RSA_EVENT


class ClientTimezoneResolutionTests(TestCase):
    def test_cloudfront_viewer_timezone_header(self):
        request = RequestFactory().get("/")
        request.META["HTTP_CLOUDFRONT_VIEWER_TIME_ZONE"] = "America/Argentina/Buenos_Aires"
        self.assertEqual(get_client_timezone_name(request), "America/Argentina/Buenos_Aires")

    def test_country_fallback_for_spain(self):
        request = RequestFactory().get("/")
        request.META["HTTP_CF_IPCOUNTRY"] = "ES"
        self.assertEqual(get_client_timezone_name(request), "Europe/Madrid")

    def test_invalid_header_falls_back_to_country(self):
        request = RequestFactory().get("/")
        request.META["HTTP_CLOUDFRONT_VIEWER_TIME_ZONE"] = "Not/A/Timezone"
        request.META["HTTP_CF_IPCOUNTRY"] = "MX"
        self.assertEqual(get_client_timezone_name(request), "America/Mexico_City")

    @override_settings(TIME_ZONE="UTC")
    def test_unknown_country_defaults_to_utc(self):
        request = RequestFactory().get("/")
        self.assertEqual(get_client_timezone_name(request), "UTC")


class ClientTimezoneMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = ClientTimezoneMiddleware(lambda request: HttpResponse("ok"))

    def test_sets_request_attributes_without_activating_global_timezone(self):
        request = self.factory.get("/")
        request.META["HTTP_CF_IPCOUNTRY"] = "AR"
        self.middleware(request)
        self.assertEqual(request.client_timezone_name, "America/Argentina/Buenos_Aires")
        self.assertTrue(request.client_timezone_label)
        self.assertEqual(timezone.get_current_timezone_name(), "UTC")


@override_settings(TIME_ZONE="UTC")
class EventKickoffLocalTimeRenderTests(TestCase):
    def setUp(self):
        normalized = normalize_world_cup_match_event(MEXICO_VS_RSA_EVENT)
        self.market, _ = import_market_from_normalized(normalized)

    def test_kickoff_renders_in_argentina_local_time(self):
        response = self.client.get(
            reverse("markets:detail", kwargs={"slug": self.market.slug}),
            HTTP_CF_IPCOUNTRY="AR",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "16:00")

    def test_kickoff_renders_in_spain_local_time(self):
        response = self.client.get(
            reverse("markets:detail", kwargs={"slug": self.market.slug}),
            HTTP_CF_IPCOUNTRY="ES",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "21:00")

    def test_close_date_stays_on_utc_calendar_day(self):
        """Non-kickoff dates must not shift with the visitor timezone."""
        from datetime import datetime, timezone as dt_timezone

        self.market.close_date = datetime(2026, 6, 11, 2, 0, tzinfo=dt_timezone.utc)
        self.market.save(update_fields=["close_date"])
        response = self.client.get(
            reverse("markets:detail", kwargs={"slug": self.market.slug}),
            HTTP_CF_IPCOUNTRY="AR",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jun 11, 2026")
        self.assertNotContains(response, "Jun 10, 2026")

    def test_timezone_display_label_for_utc(self):
        label = timezone_display_label("UTC")
        self.assertEqual(label, "UTC")
