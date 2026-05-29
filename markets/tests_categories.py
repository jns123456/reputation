from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from markets.categories import resolve_market_category_slug
from markets.models import Market
from markets.selectors import (
    blend_markets_by_source,
    filter_markets_by_browse_area,
    filter_markets_by_search,
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
        response = self.client.get(reverse("markets:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Categories")
        self.assertContains(response, "Politics")
        self.assertContains(response, 'name="q"')

    def test_market_hub_search_filters_open_events(self):
        Market.objects.create(
            external_id="hub-btc",
            title="Bitcoin hits 100k",
            slug="bitcoin-100k",
            status=Market.Status.OPEN,
        )
        Market.objects.create(
            external_id="hub-fed",
            title="Fed rate cut",
            slug="fed-rate-cut",
            status=Market.Status.OPEN,
        )
        response = self.client.get(reverse("markets:list"), {"q": "bitcoin"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bitcoin hits 100k")
        self.assertNotContains(response, "Fed rate cut")

    def test_market_hub_clear_search_returns_to_hub(self):
        Market.objects.create(
            external_id="hub-clear-btc",
            title="Bitcoin hits 100k",
            slug="bitcoin-clear-100k",
            status=Market.Status.OPEN,
        )
        response = self.client.get(reverse("markets:list"), {"q": "bitcoin"})
        self.assertContains(response, "Clear")
        clear_response = self.client.get(reverse("markets:list"))
        self.assertEqual(clear_response.status_code, 200)
        self.assertNotContains(clear_response, "Search results")

    def test_filter_markets_by_search(self):
        bitcoin = Market(
            external_id="search-btc",
            title="Bitcoin rally",
            slug="bitcoin-rally",
            category="Crypto",
        )
        fed = Market(
            external_id="search-fed",
            title="Fed decision",
            slug="fed-decision",
            category="Economy",
        )
        results = filter_markets_by_search(markets=[bitcoin, fed], search="bitcoin")
        self.assertEqual([market.slug for market in results], ["bitcoin-rally"])

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

    @patch("dashboard.views.enqueue_category_sync")
    def test_category_browse_search_filters_events(self, mock_enqueue):
        Market.objects.create(
            external_id="sport-soccer-search",
            title="World Cup final",
            slug="world-cup-final-search",
            status=Market.Status.OPEN,
            polymarket_event_raw={"tags": [{"slug": "soccer"}]},
        )
        Market.objects.create(
            external_id="sport-nba-search",
            title="NBA champion",
            slug="nba-champion-search",
            status=Market.Status.OPEN,
            polymarket_event_raw={"tags": [{"slug": "nba"}]},
        )
        response = self.client.get(
            reverse("dashboard:category_browse", kwargs={"slug": "sports"}),
            {"q": "world cup"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "World Cup final")
        self.assertNotContains(response, "NBA champion")

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


class BrowseAreaDenormalizationTests(TestCase):
    def test_browse_area_slugs_computed_on_save(self):
        market = Market.objects.create(
            external_id="denorm-nba",
            title="NBA market",
            slug="denorm-nba",
            status=Market.Status.OPEN,
            polymarket_event_raw={"tags": [{"slug": "nba"}]},
        )
        market.refresh_from_db()
        self.assertIn("nba", market.browse_area_slugs)

    def test_browse_area_slugs_recomputed_on_update(self):
        market = Market.objects.create(
            external_id="denorm-switch",
            title="Switch market",
            slug="denorm-switch",
            status=Market.Status.OPEN,
            polymarket_event_raw={"tags": [{"slug": "nba"}]},
        )
        market.polymarket_event_raw = {"tags": [{"slug": "soccer"}]}
        market.save()
        market.refresh_from_db()
        self.assertIn("soccer", market.browse_area_slugs)
        self.assertNotIn("nba", market.browse_area_slugs)

    def test_area_summaries_avoid_n_plus_one(self):
        for index in range(5):
            Market.objects.create(
                external_id=f"perf-nba-{index}",
                title=f"NBA {index}",
                slug=f"perf-nba-{index}",
                status=Market.Status.OPEN,
                polymarket_event_raw={"tags": [{"slug": "nba"}]},
            )
        # Counting from the denormalized column must be a single query
        # regardless of how many markets exist (no per-row payload fetch).
        with self.assertNumQueries(1):
            summaries = {
                item["area"].slug: item["count"]
                for item in get_browse_area_summaries(category_slug="sports")
            }
        self.assertEqual(summaries["nba"], 5)

    def test_area_filter_on_card_queryset_avoids_n_plus_one(self):
        for index in range(5):
            Market.objects.create(
                external_id=f"cardperf-nba-{index}",
                title=f"NBA {index}",
                slug=f"cardperf-nba-{index}",
                status=Market.Status.OPEN,
                polymarket_event_raw={"tags": [{"slug": "nba"}]},
            )
        markets = get_open_markets_by_canonical_category(category_slug="sports")
        # Card queryset defers raw payloads; filtering must read only the
        # denormalized column already loaded on each instance (no extra query).
        with self.assertNumQueries(0):
            filtered = filter_markets_by_browse_area(
                markets=markets,
                category_slug="sports",
                area_slug="nba",
            )
        self.assertEqual(len(filtered), 5)


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
