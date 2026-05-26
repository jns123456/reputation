from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from integrations.sync import refresh_market, refresh_stale_open_markets, sync_category_markets
from markets.categories import get_category_for_slug
from markets.models import Market


@override_settings(KALSHI_ENABLED=True)
class RefreshMarketTests(TestCase):
    @patch("integrations.sync.refresh_market_from_kalshi")
    def test_refresh_market_dispatches_kalshi(self, mock_refresh):
        market = Market(
            external_id="KXTEST",
            title="Kalshi market",
            slug="kalshi-market",
            source=Market.Source.KALSHI,
        )
        mock_refresh.return_value = market
        self.assertEqual(refresh_market(market), market)
        mock_refresh.assert_called_once_with(market)

    @patch("integrations.sync.refresh_market_from_polymarket")
    def test_refresh_market_dispatches_polymarket(self, mock_refresh):
        market = Market(
            external_id="123",
            title="Poly market",
            slug="poly-market",
            source=Market.Source.POLYMARKET,
        )
        mock_refresh.return_value = market
        self.assertEqual(refresh_market(market), market)
        mock_refresh.assert_called_once_with(market)

    @override_settings(KALSHI_ENABLED=False)
    @patch("integrations.sync.refresh_market_from_kalshi")
    def test_refresh_market_skips_kalshi_when_disabled(self, mock_refresh):
        market = Market(
            external_id="KXTEST",
            title="Kalshi market",
            slug="kalshi-market",
            source=Market.Source.KALSHI,
        )
        self.assertEqual(refresh_market(market), market)
        mock_refresh.assert_not_called()


@override_settings(KALSHI_ENABLED=True)
class SyncCategoryMarketsTests(TestCase):
    @patch("integrations.sync.sync_kalshi_markets_by_series")
    @patch("integrations.sync.sync_binary_markets_by_tag")
    def test_sync_category_uses_both_sources(self, mock_poly, mock_kalshi):
        category = get_category_for_slug("sports")
        mock_poly.return_value = {"imported": [{"created": True}], "errors": []}
        mock_kalshi.return_value = {"imported": [{"created": False}], "errors": []}

        summary = sync_category_markets(category, limit=12, kalshi_lightweight=False)

        mock_poly.assert_called_once()
        self.assertEqual(mock_kalshi.call_count, len(category.kalshi_series_tickers))
        self.assertEqual(summary.imported, 1)
        self.assertEqual(summary.updated, len(category.kalshi_series_tickers))

    @patch("integrations.sync.sync_kalshi_markets_by_series")
    @patch("integrations.sync.sync_binary_markets_by_tag")
    def test_sync_category_lightweight_limits_kalshi(self, mock_poly, mock_kalshi):
        category = get_category_for_slug("economy")
        mock_poly.return_value = {"imported": [], "errors": []}
        mock_kalshi.return_value = {"imported": [], "errors": []}

        sync_category_markets(category, kalshi_lightweight=True)

        self.assertLessEqual(mock_kalshi.call_count, 2)
        for call in mock_kalshi.call_args_list:
            kwargs = call.kwargs
            self.assertFalse(kwargs["fetch_events"])
            self.assertTrue(kwargs["include_metadata"])
            self.assertEqual(kwargs["limit"], 12)

    @patch("integrations.sync.sync_kalshi_markets_by_series")
    @patch("integrations.sync.sync_binary_markets_by_tag")
    @override_settings(KALSHI_ENABLED=False)
    def test_sync_category_skips_kalshi_when_disabled(self, mock_poly, mock_kalshi):
        category = get_category_for_slug("economy")
        mock_poly.return_value = {"imported": [{"created": True}], "errors": []}

        summary = sync_category_markets(category, limit=12)

        mock_poly.assert_called_once()
        mock_kalshi.assert_not_called()
        self.assertEqual(summary.imported, 1)


@override_settings(KALSHI_ENABLED=True)
class RefreshStaleOpenMarketsTests(TestCase):
    @patch("integrations.sync.refresh_market")
    def test_refresh_stale_open_markets(self, mock_refresh):
        stale_time = timezone.now() - timedelta(hours=2)
        market = Market.objects.create(
            external_id="stale-kalshi",
            title="Stale market",
            slug="stale-market",
            source=Market.Source.KALSHI,
            status=Market.Status.OPEN,
            kalshi_synced_at=stale_time,
        )
        Market.objects.create(
            external_id="fresh-kalshi",
            title="Fresh market",
            slug="fresh-market",
            source=Market.Source.KALSHI,
            status=Market.Status.OPEN,
            kalshi_synced_at=timezone.now(),
        )

        result = refresh_stale_open_markets(batch_size=10, stale_minutes=30)

        self.assertEqual(result["refreshed"], 1)
        mock_refresh.assert_called_once_with(market)
