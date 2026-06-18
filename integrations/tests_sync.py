from datetime import timedelta
from unittest.mock import patch

import requests
from django.test import TestCase
from django.utils import timezone

from integrations.sync import (
    refresh_market,
    refresh_stale_open_markets,
    sync_all_category_markets,
    sync_category_markets,
)
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
    @patch("integrations.services.sync_f1_markets")
    @patch("integrations.services.sync_h2h_match_markets")
    @patch("integrations.sync.sync_binary_markets_by_tag")
    def test_sync_category_imports_from_polymarket(self, mock_poly, mock_h2h, mock_f1):
        category = get_category_for_slug("sports")
        mock_poly.return_value = {"imported": [{"created": True}], "errors": []}
        mock_h2h.return_value = {"imported": [], "errors": []}
        mock_f1.return_value = {"imported": [], "errors": []}

        summary = sync_category_markets(category, limit=12)

        mock_h2h.assert_called_once()
        mock_f1.assert_called_once()
        mock_poly.assert_called_once()
        self.assertEqual(summary.imported, 1)

    @patch("integrations.sync.sync_binary_markets_by_tag")
    @patch("integrations.services.sync_f1_markets")
    @patch("integrations.services.sync_h2h_match_markets")
    def test_sports_sync_logs_transient_timeout_as_warning(
        self, mock_h2h, mock_f1, mock_poly
    ):
        category = get_category_for_slug("sports")
        mock_h2h.side_effect = requests.exceptions.ReadTimeout("read timed out")
        mock_poly.return_value = {"imported": [], "errors": []}

        with self.assertLogs("integrations.services", level="WARNING") as logs:
            summary = sync_category_markets(category, limit=12)

        self.assertEqual(summary.imported, 0)
        self.assertTrue(
            any("H2H/F1 sports sync failed for category sports" in msg for msg in logs.output)
        )
        mock_f1.assert_not_called()


class SyncAllCategoryMarketsTests(TestCase):
    @patch("integrations.sync.sync_category_markets")
    @patch("integrations.sync.sync_top_volume_polymarket_markets")
    def test_top_volume_sync_logs_transient_timeout_as_warning(
        self, mock_top_volume, mock_category
    ):
        mock_top_volume.side_effect = requests.exceptions.ReadTimeout("read timed out")
        mock_category.return_value = type(
            "Summary",
            (),
            {"imported": 0, "updated": 0, "errors": []},
        )()

        with self.assertLogs("integrations.services", level="WARNING") as logs:
            result = sync_all_category_markets(limit=5)

        self.assertEqual(result["imported"], 0)
        self.assertTrue(
            any("Polymarket top-volume sync failed" in msg for msg in logs.output)
        )


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

    @patch("integrations.sync.refresh_market")
    def test_refresh_stale_includes_closed_unresolved_markets(self, mock_refresh):
        market = Market.objects.create(
            external_id="closed-unresolved",
            title="Closed but unresolved",
            slug="closed-unresolved",
            source=Market.Source.POLYMARKET,
            status=Market.Status.CLOSED,
            resolved_outcome="",
            polymarket_synced_at=timezone.now(),
        )

        result = refresh_stale_open_markets(batch_size=10, stale_minutes=30)

        self.assertEqual(result["refreshed"], 1)
        mock_refresh.assert_called_once_with(market)

    @patch("integrations.sync.refresh_market")
    def test_refresh_stale_open_markets_prioritizes_elapsed_markets(self, mock_refresh):
        recent_sync = timezone.now() - timedelta(minutes=1)
        market = Market.objects.create(
            external_id="elapsed-poly",
            title="Elapsed market",
            slug="elapsed-market",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            close_date=timezone.now() - timedelta(minutes=2),
            polymarket_synced_at=recent_sync,
        )

        result = refresh_stale_open_markets(batch_size=10, stale_minutes=30)

        self.assertEqual(result["refreshed"], 1)
        mock_refresh.assert_called_once_with(market)
