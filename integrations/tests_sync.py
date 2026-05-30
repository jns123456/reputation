from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from integrations.sync import refresh_market, refresh_stale_open_markets, sync_category_markets
from markets.categories import get_category_for_slug
from markets.models import Market


class RefreshMarketTests(TestCase):
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


class SyncCategoryMarketsTests(TestCase):
    @patch("integrations.sync.sync_binary_markets_by_tag")
    def test_sync_category_imports_from_polymarket(self, mock_poly):
        category = get_category_for_slug("sports")
        mock_poly.return_value = {"imported": [{"created": True}], "errors": []}

        summary = sync_category_markets(category, limit=12)

        mock_poly.assert_called_once()
        self.assertEqual(summary.imported, 1)


class RefreshStaleOpenMarketsTests(TestCase):
    @patch("integrations.sync.refresh_market")
    def test_refresh_stale_open_markets(self, mock_refresh):
        stale_time = timezone.now() - timedelta(hours=2)
        market = Market.objects.create(
            external_id="stale-poly",
            title="Stale market",
            slug="stale-market",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            polymarket_synced_at=stale_time,
        )
        Market.objects.create(
            external_id="fresh-poly",
            title="Fresh market",
            slug="fresh-market",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            polymarket_synced_at=timezone.now(),
        )

        result = refresh_stale_open_markets(batch_size=10, stale_minutes=30)

        self.assertEqual(result["refreshed"], 1)
        mock_refresh.assert_called_once_with(market)
