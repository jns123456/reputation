from django.test import TestCase

from integrations.polymarket.urls import resolve_polymarket_market_url, resolve_polymarket_public_url
from markets.models import Market


class PolymarketUrlTests(TestCase):
    def test_grouped_market_fallback_to_market_url(self):
        market = Market(
            polymarket_slug="will-nvidia-be-the-largest-company-in-the-world-by-market-cap-on-may-31-971",
            slug="nvidia",
            source=Market.Source.POLYMARKET,
            polymarket_raw={
                "slug": "will-nvidia-be-the-largest-company-in-the-world-by-market-cap-on-may-31-971",
                "groupItemTitle": "NVIDIA",
            },
        )
        url = resolve_polymarket_public_url(market)
        self.assertEqual(
            url,
            "https://polymarket.com/market/will-nvidia-be-the-largest-company-in-the-world-by-market-cap-on-may-31-971",
        )

    def test_grouped_market_links_to_parent_event_when_known(self):
        market = Market(
            polymarket_slug="will-nvidia-be-the-largest-company-in-the-world-by-market-cap-on-may-31-971",
            slug="nvidia",
            source=Market.Source.POLYMARKET,
            polymarket_raw={
                "slug": "will-nvidia-be-the-largest-company-in-the-world-by-market-cap-on-may-31-971",
                "events": [{"slug": "largest-company-end-of-may-167"}],
            },
        )
        url = resolve_polymarket_public_url(market)
        self.assertEqual(url, "https://polymarket.com/event/largest-company-end-of-may-167")

    def test_standalone_market_links_to_event_page(self):
        market = Market(
            polymarket_slug="strait-of-hormuz-traffic-returns-to-normal-by-end-of-june",
            slug="strait-of-hormuz-traffic-returns-to-normal-by-end-of-june",
            source=Market.Source.POLYMARKET,
            polymarket_raw={"slug": "strait-of-hormuz-traffic-returns-to-normal-by-end-of-june"},
            polymarket_event_raw={"slug": "strait-of-hormuz-traffic-returns-to-normal-by-end-of-june"},
        )
        url = resolve_polymarket_public_url(market)
        self.assertEqual(
            url,
            "https://polymarket.com/event/strait-of-hormuz-traffic-returns-to-normal-by-end-of-june",
        )

    def test_market_outcome_url(self):
        market = Market(
            polymarket_slug="will-nvidia-be-the-largest-company-in-the-world-by-market-cap-on-may-31-971",
            slug="nvidia",
            source=Market.Source.POLYMARKET,
        )
        url = resolve_polymarket_market_url(market)
        self.assertEqual(
            url,
            "https://polymarket.com/market/will-nvidia-be-the-largest-company-in-the-world-by-market-cap-on-may-31-971",
        )
