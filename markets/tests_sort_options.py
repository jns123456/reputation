from datetime import timedelta

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from markets.models import Market
from markets.selectors import get_markets_for_display
from markets.sort_options import (
    SORT_ENDING_SOON,
    SORT_LIQUIDITY,
    SORT_NEWEST,
    SORT_TRENDING,
    SORT_VOLUME,
    market_sort_metric,
    market_volume,
    normalize_sort_filter,
    sort_markets,
)


class SortFilterNormalizationTests(SimpleTestCase):
    def test_normalize_sort_filter(self):
        self.assertEqual(normalize_sort_filter("trending"), SORT_TRENDING)
        self.assertEqual(normalize_sort_filter("volume"), SORT_VOLUME)
        self.assertEqual(normalize_sort_filter("invalid"), "")
        self.assertEqual(normalize_sort_filter(""), "")


class MarketSortMetricTests(TestCase):
    def test_market_volume_prefers_total_volume_fields(self):
        market = Market(
            external_id="sort-1",
            title="Volume test",
            slug="volume-test",
            polymarket_raw={"volumeNum": 5000, "volume24hr": 900},
        )
        self.assertEqual(market_volume(market), 5000.0)
        self.assertEqual(market_sort_metric(market, SORT_TRENDING), 900.0)

    def test_liquidity_from_event_payload(self):
        market = Market(
            external_id="sort-2",
            title="Liquidity test",
            slug="liquidity-test",
            polymarket_event_raw={"liquidity": 12000},
        )
        self.assertEqual(market_sort_metric(market, SORT_LIQUIDITY), 12000.0)

    def test_volume_does_not_use_event_total_as_fallback(self):
        market = Market(
            external_id="sort-3",
            title="Volume test",
            slug="volume-event-fallback",
            polymarket_raw={},
            polymarket_event_raw={"volumeNum": 999999, "volume": 999999},
        )
        self.assertEqual(market_sort_metric(market, SORT_VOLUME), 0.0)
        self.assertEqual(market_volume(market), 0.0)


class SortMarketsTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.low_volume = Market.objects.create(
            external_id="sort-low",
            title="Low volume",
            slug="sort-low",
            status=Market.Status.OPEN,
            polymarket_raw={"volumeNum": 100, "volume24hr": 10},
            created_at=now - timedelta(days=2),
        )
        self.high_volume = Market.objects.create(
            external_id="sort-high",
            title="High volume",
            slug="sort-high",
            status=Market.Status.OPEN,
            polymarket_raw={"volumeNum": 5000, "volume24hr": 500},
            created_at=now - timedelta(days=1),
        )
        self.high_liquidity = Market.objects.create(
            external_id="sort-liq",
            title="High liquidity",
            slug="sort-liq",
            status=Market.Status.OPEN,
            polymarket_raw={"volumeNum": 200, "liquidityNum": 9000},
            created_at=now,
        )
        self.ending_soon = Market.objects.create(
            external_id="sort-soon",
            title="Ending soon",
            slug="sort-soon",
            status=Market.Status.OPEN,
            polymarket_raw={"volumeNum": 50},
            close_date=now + timedelta(days=1),
            created_at=now - timedelta(days=3),
        )

    def test_sort_by_total_volume(self):
        ordered = sort_markets(
            [self.low_volume, self.high_volume, self.high_liquidity],
            sort=SORT_VOLUME,
        )
        self.assertEqual([market.slug for market in ordered], ["sort-high", "sort-liq", "sort-low"])

    def test_sort_by_trending_volume(self):
        ordered = sort_markets(
            [self.low_volume, self.high_volume],
            sort=SORT_TRENDING,
        )
        self.assertEqual([market.slug for market in ordered], ["sort-high", "sort-low"])

    def test_sort_by_liquidity(self):
        ordered = sort_markets(
            [self.low_volume, self.high_volume, self.high_liquidity],
            sort=SORT_LIQUIDITY,
        )
        self.assertEqual([market.slug for market in ordered], ["sort-liq", "sort-high", "sort-low"])

    def test_sort_by_newest(self):
        ordered = sort_markets(
            [self.low_volume, self.high_volume, self.high_liquidity],
            sort=SORT_NEWEST,
        )
        self.assertEqual([market.slug for market in ordered], ["sort-liq", "sort-high", "sort-low"])

    def test_sort_by_ending_soon(self):
        ordered = sort_markets(
            [self.high_volume, self.ending_soon],
            sort=SORT_ENDING_SOON,
        )
        self.assertEqual([market.slug for market in ordered], ["sort-soon", "sort-high"])


class GetMarketsForDisplaySortTests(TestCase):
    @override_settings(KALSHI_ENABLED=True)
    def test_explicit_sort_overrides_source_blend(self):
        poly = Market.objects.create(
            external_id="display-poly",
            title="Poly",
            slug="display-poly",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            polymarket_raw={"volumeNum": 100},
        )
        kalshi = Market.objects.create(
            external_id="display-kalshi",
            title="Kalshi",
            slug="display-kalshi",
            source=Market.Source.KALSHI,
            status=Market.Status.OPEN,
            kalshi_raw={"volume_fp": "10000"},
        )
        ordered = get_markets_for_display(sort=SORT_VOLUME, limit=10)
        self.assertEqual([market.slug for market in ordered[:2]], ["display-kalshi", "display-poly"])
