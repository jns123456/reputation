from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

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
            polymarket_event_raw={"tags": [{"slug": "fifa-world-cup"}]},
        )
        self.assertEqual(resolve_market_category_slug(market), "fifa-world-cup-2026")

    def test_friendly_soccer_match_resolves_to_sports_category(self):
        market = Market(
            external_id="wc-match:fif-col-cri-2026-06-01",
            title="Colombia vs Costa Rica",
            slug="colombia-vs-costa-rica",
            polymarket_raw={"market_kind": "soccer_match_3way"},
            polymarket_event_raw={"tags": [{"slug": "fifa-friendlies"}]},
        )
        self.assertEqual(resolve_market_category_slug(market), "sports")

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

    def test_category_summaries_sports_includes_world_cup_matches(self):
        Market.objects.create(
            external_id="wc-match:summary-wc",
            title="Uruguay vs. Spain",
            slug="uruguay-vs-spain-summary",
            status=Market.Status.OPEN,
            polymarket_raw={"market_kind": "soccer_match_3way"},
            polymarket_event_raw={"tags": [{"slug": "fifa-world-cup"}]},
        )
        Market.objects.create(
            external_id="summary-nba",
            title="NBA champion",
            slug="nba-champion-summary",
            status=Market.Status.OPEN,
            polymarket_event_raw={"tags": [{"slug": "nba"}]},
        )

        summaries = {item["category"].slug: item["count"] for item in get_category_summaries()}

        self.assertEqual(summaries["sports"], 2)
        self.assertEqual(summaries["fifa-world-cup-2026"], 1)

    def test_get_open_markets_by_canonical_category(self):
        markets = get_open_markets_by_canonical_category(category_slug="politics")
        self.assertEqual(len(markets), 1)
        self.assertEqual(markets[0].slug, "politics-market")

    def test_open_category_selectors_exclude_non_forecastable_markets(self):
        Market.objects.create(
            external_id="sel-econ-expired",
            title="Expired economy market",
            slug="expired-economy-market",
            category="Economy",
            status=Market.Status.OPEN,
            close_date=timezone.now() - timedelta(minutes=5),
        )
        Market.objects.create(
            external_id="sel-econ-in-play",
            title="Started economy market",
            slug="started-economy-market",
            category="Economy",
            status=Market.Status.OPEN,
            game_start_time=timezone.now() - timedelta(minutes=5),
        )
        Market.objects.create(
            external_id="sel-econ-not-accepting",
            title="Halted economy market",
            slug="halted-economy-market",
            category="Economy",
            status=Market.Status.OPEN,
            accepting_orders=False,
        )

        markets = get_open_markets_by_canonical_category(category_slug="economy")
        summaries = {item["category"].slug: item["count"] for item in get_category_summaries()}

        self.assertEqual({market.slug for market in markets}, {"economy-market"})
        self.assertEqual(summaries["economy"], 1)


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

    @patch("dashboard.views.enqueue_category_sync")
    def test_world_cup_match_gets_world_cup_games_browse_area(self, mock_enqueue):
        market = Market.objects.create(
            external_id="wc-match:denorm-wc",
            title="Uruguay vs. Spain",
            slug="uruguay-vs-spain-denorm",
            status=Market.Status.OPEN,
            polymarket_raw={"market_kind": "soccer_match_3way"},
            polymarket_event_raw={"tags": [{"slug": "fifa-world-cup"}]},
        )
        market.refresh_from_db()
        self.assertIn("world-cup-games", market.browse_area_slugs)

    @patch("dashboard.views.enqueue_category_sync")
    def test_sports_search_includes_world_cup_match_markets(self, mock_enqueue):
        Market.objects.create(
            external_id="wc-match:uruguay-cabo-verde",
            title="Uruguay vs. Cabo Verde",
            slug="uruguay-vs-cabo-verde",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Uruguay"}, {"label": "Draw"}, {"label": "Cabo Verde"}],
            polymarket_raw={"market_kind": "soccer_match_3way"},
            polymarket_event_raw={"tags": [{"slug": "fifa-world-cup"}]},
        )
        Market.objects.create(
            external_id="sport-nba-uruguay",
            title="NBA champion",
            slug="nba-champion-uruguay",
            status=Market.Status.OPEN,
            polymarket_event_raw={"tags": [{"slug": "nba"}]},
        )
        response = self.client.get(
            reverse("dashboard:category_browse", kwargs={"slug": "sports"}),
            {"q": "uruguay"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Uruguay vs. Cabo Verde")
        self.assertNotContains(response, "NBA champion")

    @patch("dashboard.views.enqueue_category_sync")
    def test_sports_browse_lists_world_cup_sub_area(self, mock_enqueue):
        Market.objects.create(
            external_id="wc-match:uruguay-spain",
            title="Uruguay vs. Spain",
            slug="uruguay-vs-spain-browse",
            status=Market.Status.OPEN,
            polymarket_raw={"market_kind": "soccer_match_3way"},
            polymarket_event_raw={"tags": [{"slug": "fifa-world-cup"}]},
        )
        response = self.client.get(
            reverse("dashboard:category_browse", kwargs={"slug": "sports"}),
            {"area": "world-cup-games"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Uruguay vs. Spain")
        self.assertContains(response, "FIFA World Cup 2026")

    @patch("dashboard.views.enqueue_category_sync")
    @override_settings(CATEGORY_BROWSE_PAGE_SIZE=2)
    def test_category_browse_pagination(self, mock_enqueue):
        for index in range(3):
            Market.objects.create(
                external_id=f"sport-page-{index}",
                title=f"Sports market {index}",
                slug=f"sports-market-{index}",
                status=Market.Status.OPEN,
                volume_total=float(100 - index),
                polymarket_event_raw={"tags": [{"slug": "soccer"}]},
            )
        response = self.client.get(reverse("dashboard:category_browse", kwargs={"slug": "sports"}))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["page_obj"].has_next)
        page_two = self.client.get(
            reverse("dashboard:category_browse", kwargs={"slug": "sports"}),
            {"page": 2},
        )
        self.assertEqual(page_two.status_code, 200)
        self.assertContains(page_two, "Next")

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
            outcomes=[{"label": "Mexico"}, {"label": "Draw"}, {"label": "South Africa"}],
            polymarket_raw={"market_kind": "soccer_match_3way"},
            polymarket_event_raw={"tags": [{"slug": "fifa-world-cup"}]},
        )
        markets = get_open_markets_by_canonical_category(category_slug="fifa-world-cup-2026")
        self.assertEqual(len(markets), 1)
        self.assertEqual(markets[0].slug, "mexico-vs-south-africa")

    def test_polymarket_tag_matches_browse_area(self):
        poly_nba = Market.objects.create(
            external_id="poly-nba-filter",
            title="NBA Polymarket",
            slug="nba-poly",
            status=Market.Status.OPEN,
            source=Market.Source.POLYMARKET,
            polymarket_raw={"tags": [{"slug": "nba"}]},
        )
        sports = get_open_markets_by_canonical_category(category_slug="sports")
        filtered = filter_markets_by_browse_area(
            markets=sports,
            category_slug="sports",
            area_slug="nba",
        )
        self.assertEqual([market.pk for market in filtered], [poly_nba.pk])

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
    def test_blend_orders_by_volume(self):
        high = Market.objects.create(
            external_id="blend-poly-high",
            title="Poly high volume",
            slug="blend-poly-high",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            polymarket_raw={"volumeNum": 1_000_000},
        )
        low = Market.objects.create(
            external_id="blend-poly-low",
            title="Poly low volume",
            slug="blend-poly-low",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            polymarket_raw={"volumeNum": 100},
        )
        blended = blend_markets_by_source([low, high], limit=2)
        self.assertEqual([market.pk for market in blended], [high.pk, low.pk])
