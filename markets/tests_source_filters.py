from django.test import SimpleTestCase
from django.urls import reverse

from markets.source_filters import build_source_filter_urls, normalize_source_filter


class SourceFilterTests(SimpleTestCase):
    def test_normalize_source_filter(self):
        self.assertEqual(normalize_source_filter("polymarket"), "polymarket")
        self.assertEqual(normalize_source_filter("invalid"), "")
        self.assertEqual(normalize_source_filter(""), "")

    def test_build_source_filter_urls_preserves_params(self):
        base = reverse("markets:list")
        urls = build_source_filter_urls(
            base_url=base,
            active_source="polymarket",
            extra={"category": "Sports", "status": "open"},
        )
        self.assertIn("source=polymarket", urls["polymarket"])
        self.assertIn("category=Sports", urls["polymarket"])
        self.assertNotIn("source=", urls["all"])
        self.assertIn("category=Sports", urls["all"])
        self.assertEqual(urls["active_source"], "polymarket")
