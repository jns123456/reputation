from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from markets.models import Market
from markets.tape_context import TAPE_MARKETS_CACHE_KEY, load_tape_markets, tape_markets_context


class TapeMarketsContextTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_load_tape_markets_uses_cache(self):
        Market.objects.create(
            external_id="tape-cache-1",
            title="Cached tape market",
            slug="cached-tape-market",
            status=Market.Status.OPEN,
            accepting_orders=True,
            close_date=timezone.now() + timedelta(days=7),
            card_image_url="https://example.com/cached.png",
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )

        first = load_tape_markets()
        Market.objects.all().delete()
        second = load_tape_markets()

        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertEqual(first[0].slug, second[0].slug)

        cache.delete(TAPE_MARKETS_CACHE_KEY)
        self.assertEqual(load_tape_markets(), [])

    def test_context_processor_exposes_markets(self):
        context = tape_markets_context(request=None)
        self.assertIn("landing_tape_markets", context)
        self.assertIsInstance(context["landing_tape_markets"], list)


class GlobalMarketTapeRenderTests(TestCase):
    def setUp(self):
        cache.clear()
        Market.objects.create(
            external_id="tape-global-1",
            title="Global tape market",
            slug="global-tape-market",
            status=Market.Status.OPEN,
            accepting_orders=True,
            close_date=timezone.now() + timedelta(days=7),
            card_image_url="https://example.com/global.png",
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )

    def test_market_hub_renders_tape(self):
        response = self.client.get(reverse("markets:list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pr-market-tape")
        self.assertContains(response, "Global tape market")
        self.assertContains(response, "/markets/global-tape-market/")

    def test_forecasts_page_renders_tape(self):
        response = self.client.get(reverse("dashboard:forecasts"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pr-market-tape")
        self.assertContains(response, "Global tape market")
