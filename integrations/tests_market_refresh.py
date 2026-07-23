from unittest.mock import MagicMock, patch

from django.db import OperationalError
from django.test import TestCase

from integrations.market_refresh import (
    attach_refresh_routing_raw,
    is_postgres_out_of_memory,
    load_market_for_refresh,
    market_raw_json_hints,
)
from integrations.tasks import refresh_market_task
from markets.models import Market


class PostgresOutOfMemoryTests(TestCase):
    def test_detects_out_of_memory_message(self):
        exc = OperationalError("out of memory\nDETAIL:  Failed on request of size 8192.")
        self.assertTrue(is_postgres_out_of_memory(exc))

    def test_ignores_other_operational_errors(self):
        exc = OperationalError("duplicate key value violates unique constraint")
        self.assertFalse(is_postgres_out_of_memory(exc))


class LoadMarketForRefreshTests(TestCase):
    def test_defers_bulky_polymarket_payloads(self):
        market = Market.objects.create(
            external_id="defer-test",
            title="Defer test",
            slug="defer-test",
            source=Market.Source.POLYMARKET,
            polymarket_raw={"market_kind": "binary", "blob": "x" * 5000},
            polymarket_event_raw={"markets": [{"id": 1}]},
        )

        loaded = load_market_for_refresh(market.pk)

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.external_id, "defer-test")
        self.assertIn("polymarket_raw", loaded.get_deferred_fields())
        self.assertIn("polymarket_event_raw", loaded.get_deferred_fields())


class MarketRawJsonHintsTests(TestCase):
    def test_extracts_routing_keys_without_loading_full_raw(self):
        market = Market.objects.create(
            external_id="hints-test",
            title="Hints test",
            slug="hints-test",
            source=Market.Source.POLYMARKET,
            polymarket_raw={
                "market_kind": "soccer_match_3way",
                "event_slug": "fif-col-cri-2026-06-01",
                "blob": "x" * 5000,
            },
        )

        hints = market_raw_json_hints(market.pk)

        self.assertEqual(hints["market_kind"], "soccer_match_3way")
        self.assertEqual(hints["event_slug"], "fif-col-cri-2026-06-01")


class AttachRefreshRoutingRawTests(TestCase):
    def test_populates_in_memory_raw_for_deferred_market(self):
        market = Market.objects.create(
            external_id="attach-test",
            title="Attach test",
            slug="attach-test",
            source=Market.Source.POLYMARKET,
            polymarket_raw={"market_kind": "soccer_match_3way", "blob": "x" * 5000},
        )
        loaded = load_market_for_refresh(market.pk)

        attach_refresh_routing_raw(loaded)

        self.assertEqual(loaded.polymarket_raw["market_kind"], "soccer_match_3way")
        self.assertNotIn("blob", loaded.polymarket_raw)


class RefreshMarketTaskTests(TestCase):
    @patch("integrations.sync.refresh_market")
    @patch("integrations.market_refresh.load_market_for_refresh")
    def test_refresh_market_task_uses_deferred_loader(self, mock_load, mock_refresh):
        market = Market(
            pk=99,
            external_id="task-test",
            title="Task test",
            slug="task-test",
            source=Market.Source.POLYMARKET,
        )
        market.get_deferred_fields = MagicMock(return_value={"polymarket_raw"})
        mock_load.return_value = market

        refresh_market_task.run(99)

        mock_load.assert_called_once_with(99)
        mock_refresh.assert_called_once_with(market)

    @patch("integrations.sync.refresh_market")
    @patch("integrations.market_refresh.load_market_for_refresh")
    def test_refresh_market_task_skips_postgres_oom_on_load(self, mock_load, mock_refresh):
        mock_load.side_effect = OperationalError("out of memory")

        refresh_market_task.run(99)

        mock_refresh.assert_not_called()

    @patch("integrations.sync.refresh_market")
    @patch("integrations.market_refresh.load_market_for_refresh")
    def test_refresh_market_task_skips_postgres_oom_on_refresh(self, mock_load, mock_refresh):
        market = Market(
            pk=99,
            external_id="task-test",
            title="Task test",
            slug="task-test",
            source=Market.Source.POLYMARKET,
        )
        mock_load.return_value = market
        mock_refresh.side_effect = OperationalError("out of memory")

        refresh_market_task.run(99)

        mock_refresh.assert_called_once_with(market)
