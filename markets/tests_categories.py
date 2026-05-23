from django.test import TestCase
from django.urls import reverse

from markets.categories import resolve_market_category_slug
from markets.models import Market
from markets.selectors import get_category_summaries, get_open_markets_by_canonical_category


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
            title="World Cup",
            slug="world-cup",
            polymarket_event_raw={"tags": [{"slug": "fifa-world-cup"}]},
        )
        self.assertEqual(resolve_market_category_slug(market), "sports")

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
        self.assertContains(response, "Economy")

    def test_category_browse_page(self):
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

    def test_unknown_category_returns_404(self):
        response = self.client.get(reverse("dashboard:category_browse", kwargs={"slug": "unknown"}))
        self.assertEqual(response.status_code, 404)
