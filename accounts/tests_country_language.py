"""Tests for country → official language detection."""

from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.utils import translation

from accounts.country_language import (
    get_country_code_from_request,
    language_for_request_country,
    official_language_for_country,
)
from accounts.middleware import CountryLanguageMiddleware


class OfficialLanguageMappingTests(TestCase):
    def test_spanish_official_countries(self):
        self.assertEqual(official_language_for_country("ES"), "es")
        self.assertEqual(official_language_for_country("MX"), "es")
        self.assertEqual(official_language_for_country("AR"), "es")

    def test_other_countries_default_to_english(self):
        self.assertEqual(official_language_for_country("US"), "en")
        self.assertEqual(official_language_for_country("FR"), "en")
        self.assertEqual(official_language_for_country("BR"), "en")

    def test_invalid_country_returns_none(self):
        self.assertIsNone(official_language_for_country(None))
        self.assertIsNone(official_language_for_country("ZZZ"))


class CountryHeaderTests(TestCase):
    def test_cloudflare_country_header(self):
        request = RequestFactory().get("/")
        request.META["HTTP_CF_IPCOUNTRY"] = "ES"
        self.assertEqual(get_country_code_from_request(request), "ES")
        self.assertEqual(language_for_request_country(request), "es")

    def test_cloudfront_country_header(self):
        request = RequestFactory().get("/")
        request.META["HTTP_CLOUDFRONT_VIEWER_COUNTRY"] = "US"
        self.assertEqual(get_country_code_from_request(request), "US")
        self.assertEqual(language_for_request_country(request), "en")


@override_settings(LANGUAGE_CODE="en")
class CountryLanguageMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = CountryLanguageMiddleware(lambda request: HttpResponse("ok"))

    def test_activates_language_and_sets_cookie(self):
        request = self.factory.get("/")
        request.META["HTTP_CF_IPCOUNTRY"] = "ES"
        response = self.middleware(request)
        self.assertEqual(translation.get_language(), "es")
        self.assertEqual(response.cookies["django_language"].value, "es")

    def test_skips_when_language_cookie_present(self):
        request = self.factory.get("/")
        request.COOKIES["django_language"] = "en"
        request.META["HTTP_CF_IPCOUNTRY"] = "ES"
        response = self.middleware(request)
        self.assertNotIn("django_language", response.cookies)

    def test_integration_sets_spanish_for_mexico(self):
        response = self.client.get("/", HTTP_CF_IPCOUNTRY="MX")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.cookies["django_language"].value, "es")
        self.assertEqual(translation.get_language(), "es")
