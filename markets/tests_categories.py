from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from markets.categories import resolve_market_category_slug
from markets.models import Market
from markets.selectors import (
    blend_markets_by_source,
    filter_markets_by_browse_area,
    get_browse_area_summaries,
    get_category_summaries,
    get_open_markets_by_canonical_category,
)


class MarketCategoryResolutionTests(TestCase):
    def test_economy_from_category_field(self):
        market = Market(
            external_id="cat-econ",
            title="Fed cut",
            slug="fed-cut",
            category="Economy",
        )
        self.assertEqual(resolve_market_category_slug(market), "economy")

    def test_politics_from_event_tags(self):
        market = Market(
            external_id="cat-pol",
            title="Election",
            slug="election",
            polymarket_event_raw={
                "tags": [{"slug": "politics"}, {"slug": "elections"}],
            },
        )
        self.assertEqual(resolve_market_category_slug(market), "politics")

    def test_sports_from_tags(self):
        market = Market(
            external_id="cat-sport",
            title="World Cup winner",
            slug="world-cup-winner",
            polymarket_event_raw={"tags": [{"slug": "fifa-world-cup"}]},
        )
        self.assertEqual(resolve_market_category_slug(market), "sports")

    def test_world_cup_match_market_resolves_to_world_cup_category(self):
        market = Market(
            external_id="wc-match:fifwc-mex-rsa-2026-06-11",
            title="Mexico vs. South Africa",
            slug="mexico-vs-south-africa",
            polymarket_raw={"market_kind": "soccer_match_3way"},
        )
        self.assertEqual(resolve_market_category_slug(market), "fifa-world-cup-2026")

    def test_crypto_wins_over_economy_when_both_tags_present(self):
        market = Market(
            external_id="cat-btc",
            title="MicroStrategy sells Bitcoin",
            slug="mstr-btc",
            category="Economy",
            polymarket_event_raw={
                "tags": [{"slug": "crypto"}, {"slug": "economy"}],
            },
        )
        self.assertEqual(resolve_market_category_slug(market), "crypto")

    def test_other_when_unmatched(self):
        market = Market(
            external_id="cat-other",
            title="Random",
            slug="random",
            category="Some niche label",
        )
        self.assertEqual(resolve_market_category_slug(market), "other")

    def test_kalshi_event_category_maps_to_sports(self):
        market = Market(
            external_id="kalshi-sport",
            title="NBA game",
            slug="nba-game",
            source=Market.Source.KALSHI,
            kalshi_event_raw={"event": {"category": "Sports", "series_ticker": "KXNBAGAME"}},
        )
        self.assertEqual(resolve_market_category_slug(market), "sports")


class MarketCategorySelectorTests(TestCase):
    def setUp(self):
        Market.objects.create(
            external_id="sel-econ-1",
            title="Economy market",
            slug="economy-market",
            category="Economy",
            status=Market.Status.OPEN,
        )
        Market.objects.create(
            external_id="sel-pol-1",
            title="Politics market",
            slug="politics-market",
            status=Market.Status.OPEN,
            polymarket_event_raw={"tags": [{"slug": "politics"}]},
        )
        Market.objects.create(
            external_id="sel-closed",
            title="Closed market",
            slug="closed-market",
            category="Economy",
            status=Market.Status.CLOSED,
        )

    def test_category_summaries_count_open_markets(self):
        summaries = {item["category"].slug: item["count"] for item in get_category_summaries()}
        self.assertEqual(summaries["economy"], 1)
        self.assertEqual(summaries["politics"], 1)

    def test_get_open_markets_by_canonical_category(self):
        markets = get_open_markets_by_canonical_category(category_slug="politics")
        self.assertEqual(len(markets), 1)
        self.assertEqual(markets[0].slug, "politics-market")


class CategoryBrowseViewTests(TestCase):
    def test_landing_renders_category_cards(self):
        Market.objects.create(
            external_id="view-econ",
            title="GDP growth",
            slug="gdp-growth",
            category="Economy",
            status=Market.Status.OPEN,
        )
        response = self.client.get(reverse("dashboard:landing"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Explore by category")
        self.assertContains(response, "FIFA World Cup 2026")

    @patch("dashboard.views.enqueue_category_sync")
    def test_category_browse_page(self, mock_enqueue):
        Market.objects.create(
            external_id="view-pol",
            title="Primary winner",
            slug="primary-winner",
            status=Market.Status.OPEN,
            polymarket_event_raw={"tags": [{"slug": "politics"}]},
        )
        response = self.client.get(reverse("dashboard:category_browse", kwargs={"slug": "politics"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Politics")
        self.assertContains(response, "Primary winner")

    @patch("dashboard.views.enqueue_category_sync")
    def test_category_browse_area_filter(self, mock_enqueue):
        Market.objects.create(
            external_id="sport-soccer",
            title="World Cup final",
            slug="world-cup-final",
            status=Market.Status.OPEN,
            polymarket_event_raw={"tags": [{"slug": "soccer"}, {"slug": "fifa-world-cup"}]},
        )
        Market.objects.create(
            external_id="sport-nba",
            title="NBA champion",
            slug="nba-champion-market",
            status=Market.Status.OPEN,
            polymarket_event_raw={"tags": [{"slug": "nba"}]},
        )
        response = self.client.get(
            reverse("dashboard:category_browse", kwargs={"slug": "sports"}),
            {"area": "soccer"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "World Cup final")
        self.assertNotContains(response, "NBA champion")
        self.assertContains(response, "Soccer")

    def test_browse_area_summaries(self):
        Market.objects.create(
            external_id="area-nba",
            title="NBA market",
            slug="nba-market",
            status=Market.Status.OPEN,
            polymarket_event_raw={"tags": [{"slug": "nba"}]},
        )
        Market.objects.create(
            external_id="area-soccer",
            title="Soccer market",
            slug="soccer-market",
            status=Market.Status.OPEN,
            polymarket_event_raw={"tags": [{"slug": "soccer"}]},
        )
        summaries = {item["area"].slug: item["count"] for item in get_browse_area_summaries(category_slug="sports")}
        self.assertEqual(summaries["nba"], 1)
        self.assertEqual(summaries["soccer"], 1)

    def test_filter_markets_by_browse_area(self):
        nba = Market.objects.create(
            external_id="filter-nba",
            title="NBA",
            slug="nba-only",
            status=Market.Status.OPEN,
            polymarket_event_raw={"tags": [{"slug": "nba"}]},
        )
        Market.objects.create(
            external_id="filter-soccer",
            title="Soccer",
            slug="soccer-only",
            status=Market.Status.OPEN,
            polymarket_event_raw={"tags": [{"slug": "soccer"}]},
        )
        sports = get_open_markets_by_canonical_category(category_slug="sports")
        filtered = filter_markets_by_browse_area(
            markets=sports,
            category_slug="sports",
            area_slug="nba",
        )
        self.assertEqual([market.pk for market in filtered], [nba.pk])

    def test_world_cup_category_lists_match_markets(self):
        Market.objects.create(
            external_id="wc-match:fifwc-mex-rsa-2026-06-11",
            title="Mexico vs. South Africa",
            slug="mexico-vs-south-africa",
            status=Market.Status.OPEN,
            canonical_category_slug="fifa-world-cup-2026",
            outcomes=[{"label": "Mexico"}, {"label": "Draw"}, {"label": "South Africa"}],
            polymarket_raw={"market_kind": "soccer_match_3way"},
        )
        markets = get_open_markets_by_canonical_category(category_slug="fifa-world-cup-2026")
        self.assertEqual(len(markets), 1)
        self.assertEqual(markets[0].slug, "mexico-vs-south-africa")

    def test_kalshi_series_matches_browse_area(self):
        kalshi_nba = Market.objects.create(
            external_id="kalshi-nba-filter",
            title="NBA Kalshi",
            slug="nba-kalshi",
            status=Market.Status.OPEN,
            source=Market.Source.KALSHI,
            kalshi_event_raw={"event": {"category": "Sports", "series_ticker": "KXNBAGAME"}},
        )
        sports = get_open_markets_by_canonical_category(category_slug="sports")
        filtered = filter_markets_by_browse_area(
            markets=sports,
            category_slug="sports",
            area_slug="nba",
        )
        self.assertEqual([market.pk for market in filtered], [kalshi_nba.pk])

    def test_unknown_category_returns_404(self):
        response = self.client.get(reverse("dashboard:category_browse", kwargs={"slug": "unknown"}))
        self.assertEqual(response.status_code, 404)


class BlendMarketsBySourceTests(TestCase):
    def test_blend_includes_both_sources(self):
        poly = Market.objects.create(
            external_id="blend-poly",
            title="Poly high volume",
            slug="blend-poly",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            polymarket_raw={"volumeNum": 1_000_000},
        )
        kalshi = Market.objects.create(
            external_id="blend-kalshi",
            title="Kalshi market",
            slug="blend-kalshi",
            source=Market.Source.KALSHI,
            status=Market.Status.OPEN,
            kalshi_raw={"volume_fp": "100"},
        )
        blended = blend_markets_by_source([poly, kalshi], limit=2)
        sources = {market.source for market in blended}
        self.assertEqual(sources, {Market.Source.POLYMARKET, Market.Source.KALSHI})
