from io import StringIO

from datetime import datetime, timezone as dt_timezone

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from integrations.polymarket.urls import resolve_polymarket_public_url
from markets.composite_redirect import is_orphan_polymarket_leg
from markets.forecast_modes import ForecastMode, get_forecast_mode
from markets.models import Market
from markets.prune_services import (
    PRUNED_MARKER,
    compact_polymarket_raw_payloads,
    market_raw_is_already_pruned,
    market_raw_needs_pruning,
    prune_market_raw_batch,
    prune_market_raw_queryset,
    run_market_raw_prune,
)
from markets.tasks import prune_market_raw_fifo_task


class CompactPolymarketRawTests(TestCase):
    def _make_market(self, **kwargs):
        defaults = {
            "external_id": "pm-123",
            "title": "Test market",
            "slug": "test-market",
            "source": Market.Source.POLYMARKET,
            "status": Market.Status.RESOLVED,
            "polymarket_slug": "test-market-slug",
            "polymarket_raw": {
                "slug": "test-market-slug",
                "groupItemTitle": "Candidate A",
                "market_kind": "polymarket_multi_outcome_event",
                "events": [{"slug": "parent-event-slug", "title": "Huge parent"}],
                "description": "x" * 5000,
                "markets": [{"id": "1"}, {"id": "2"}],
            },
            "polymarket_event_raw": {
                "slug": "parent-event-slug",
                "title": "Parent event",
                "markets": [{"id": "1", "question": "q"} for _ in range(50)],
                "tags": [{"slug": "politics"}],
            },
        }
        defaults.update(kwargs)
        return Market.objects.create(**defaults)

    def test_compact_preserves_polymarket_urls(self):
        market = self._make_market()
        new_raw, new_event = compact_polymarket_raw_payloads(market)
        market.polymarket_raw = new_raw
        market.polymarket_event_raw = new_event

        self.assertEqual(
            resolve_polymarket_public_url(market),
            "https://polymarket.com/event/parent-event-slug",
        )
        self.assertEqual(new_raw["groupItemTitle"], "Candidate A")
        self.assertEqual(new_event["slug"], "parent-event-slug")
        self.assertNotIn("markets", new_event)

    def test_compact_preserves_forecast_and_orphan_hints(self):
        market = self._make_market(
            polymarket_raw={
                "slug": "will-colombia-win",
                "sportsMarketType": "moneyline",
                "question": "Will Colombia win?",
                "noise": {"nested": list(range(100))},
            },
            polymarket_event_raw={
                "slug": "colombia-vs-costa-rica",
                "markets": [{"sportsMarketType": "moneyline"}],
            },
        )
        new_raw, new_event = compact_polymarket_raw_payloads(market)
        market.polymarket_raw = new_raw
        market.polymarket_event_raw = new_event

        self.assertEqual(get_forecast_mode(market), ForecastMode.BINARY)
        self.assertTrue(is_orphan_polymarket_leg(market))
        self.assertEqual(new_event["slug"], "colombia-vs-costa-rica")

    def test_needs_pruning_skips_already_pruned(self):
        market = self._make_market(
            polymarket_raw={PRUNED_MARKER: "2026-07-07", "slug": "x"},
            polymarket_event_raw={PRUNED_MARKER: "2026-07-07", "slug": "x"},
        )
        self.assertTrue(market_raw_is_already_pruned(market))
        self.assertFalse(market_raw_needs_pruning(market))

    def test_batch_prune_writes_minimal_payloads(self):
        market = self._make_market()
        stats = prune_market_raw_batch([market], dry_run=False)

        self.assertEqual(stats["updated"], 1)
        market.refresh_from_db()
        self.assertIn(PRUNED_MARKER, market.polymarket_raw)
        self.assertTrue(market_raw_is_already_pruned(market))
        self.assertFalse(market_raw_needs_pruning(market))

    def test_batch_dry_run_does_not_persist(self):
        market = self._make_market()
        stats = prune_market_raw_batch([market], dry_run=True)

        self.assertEqual(stats["updated"], 1)
        market.refresh_from_db()
        self.assertIn("markets", market.polymarket_event_raw)


class FifoPruneTests(TestCase):
    def _bloated_raw(self, slug: str) -> dict:
        return {"slug": slug, "blob": "x" * 2000}

    def test_queryset_orders_oldest_resolved_first(self):
        older = Market.objects.create(
            external_id="fifo-old",
            title="Older",
            slug="fifo-old",
            source=Market.Source.POLYMARKET,
            status=Market.Status.RESOLVED,
            resolution_date=datetime(2024, 1, 1, tzinfo=dt_timezone.utc),
            polymarket_raw=self._bloated_raw("fifo-old"),
            polymarket_event_raw={"slug": "fifo-old"},
        )
        newer = Market.objects.create(
            external_id="fifo-new",
            title="Newer",
            slug="fifo-new",
            source=Market.Source.POLYMARKET,
            status=Market.Status.RESOLVED,
            resolution_date=datetime(2026, 1, 1, tzinfo=dt_timezone.utc),
            polymarket_raw=self._bloated_raw("fifo-new"),
            polymarket_event_raw={"slug": "fifo-new"},
        )

        ordered = list(
            prune_market_raw_queryset(order="fifo").values_list("pk", flat=True)
        )
        self.assertEqual(ordered, [older.pk, newer.pk])

    def test_run_market_raw_prune_fifo_respects_limit(self):
        older = Market.objects.create(
            external_id="fifo-old-run",
            title="Older run",
            slug="fifo-old-run",
            source=Market.Source.POLYMARKET,
            status=Market.Status.RESOLVED,
            resolution_date=datetime(2024, 6, 1, tzinfo=dt_timezone.utc),
            polymarket_raw=self._bloated_raw("fifo-old-run"),
            polymarket_event_raw={"slug": "fifo-old-run"},
        )
        newer = Market.objects.create(
            external_id="fifo-new-run",
            title="Newer run",
            slug="fifo-new-run",
            source=Market.Source.POLYMARKET,
            status=Market.Status.RESOLVED,
            resolution_date=datetime(2026, 6, 1, tzinfo=dt_timezone.utc),
            polymarket_raw=self._bloated_raw("fifo-new-run"),
            polymarket_event_raw={"slug": "fifo-new-run"},
        )

        stats = run_market_raw_prune(limit=1, order="fifo")
        self.assertEqual(stats["updated"], 1)

        older.refresh_from_db()
        newer.refresh_from_db()
        self.assertTrue(market_raw_is_already_pruned(older))
        self.assertFalse(market_raw_is_already_pruned(newer))

    @override_settings(MARKET_RAW_PRUNE_ENABLED=True, MARKET_RAW_PRUNE_BATCH_SIZE=1)
    def test_fifo_task_compacts_oldest_batch(self):
        older = Market.objects.create(
            external_id="fifo-task-old",
            title="Older task",
            slug="fifo-task-old",
            source=Market.Source.POLYMARKET,
            status=Market.Status.RESOLVED,
            resolution_date=datetime(2023, 1, 1, tzinfo=dt_timezone.utc),
            polymarket_raw=self._bloated_raw("fifo-task-old"),
            polymarket_event_raw={"slug": "fifo-task-old"},
        )
        newer = Market.objects.create(
            external_id="fifo-task-new",
            title="Newer task",
            slug="fifo-task-new",
            source=Market.Source.POLYMARKET,
            status=Market.Status.RESOLVED,
            resolution_date=datetime(2026, 2, 1, tzinfo=dt_timezone.utc),
            polymarket_raw=self._bloated_raw("fifo-task-new"),
            polymarket_event_raw={"slug": "fifo-task-new"},
        )

        prune_market_raw_fifo_task()

        older.refresh_from_db()
        newer.refresh_from_db()
        self.assertTrue(market_raw_is_already_pruned(older))
        self.assertFalse(market_raw_is_already_pruned(newer))

    @override_settings(MARKET_RAW_PRUNE_ENABLED=False)
    def test_fifo_task_skips_when_disabled(self):
        market = Market.objects.create(
            external_id="fifo-disabled",
            title="Disabled",
            slug="fifo-disabled",
            source=Market.Source.POLYMARKET,
            status=Market.Status.RESOLVED,
            polymarket_raw=self._bloated_raw("fifo-disabled"),
            polymarket_event_raw={"slug": "fifo-disabled"},
        )

        prune_market_raw_fifo_task()

        market.refresh_from_db()
        self.assertIn("blob", market.polymarket_raw)


class PruneMarketRawCommandTests(TestCase):
    def test_command_dry_run_reports_candidates(self):
        Market.objects.create(
            external_id="resolved-1",
            title="Resolved",
            slug="resolved-1",
            source=Market.Source.POLYMARKET,
            status=Market.Status.RESOLVED,
            polymarket_raw={"slug": "resolved-1", "blob": "x" * 2000},
            polymarket_event_raw={"slug": "resolved-1", "blob": "y" * 2000},
        )
        out = StringIO()
        call_command("prune_market_raw", "--dry-run", stdout=out)

        market = Market.objects.get(external_id="resolved-1")
        self.assertIn("blob", market.polymarket_raw)
        self.assertIn("Would compact", out.getvalue())

    def test_command_prunes_resolved_markets(self):
        Market.objects.create(
            external_id="resolved-2",
            title="Resolved two",
            slug="resolved-2",
            source=Market.Source.POLYMARKET,
            status=Market.Status.RESOLVED,
            polymarket_slug="resolved-2",
            polymarket_raw={"slug": "resolved-2", "blob": "x" * 2000},
            polymarket_event_raw={"slug": "resolved-2", "blob": "y" * 2000},
        )
        call_command("prune_market_raw", stdout=StringIO())

        market = Market.objects.get(external_id="resolved-2")
        self.assertTrue(market_raw_is_already_pruned(market))
        self.assertNotIn("blob", market.polymarket_raw)

    def test_command_refuses_open_without_flag(self):
        Market.objects.create(
            external_id="open-1",
            title="Open",
            slug="open-1",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            polymarket_raw={"slug": "open-1", "blob": "x" * 2000},
            polymarket_event_raw={"slug": "open-1"},
        )
        with self.assertRaises(CommandError):
            call_command("prune_market_raw", "--status", "open", stdout=StringIO())

    def test_command_leaves_open_markets_untouched_by_default(self):
        Market.objects.create(
            external_id="open-2",
            title="Open two",
            slug="open-2",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            polymarket_raw={"slug": "open-2", "blob": "x" * 2000},
            polymarket_event_raw={"slug": "open-2"},
        )
        call_command("prune_market_raw", stdout=StringIO())

        market = Market.objects.get(external_id="open-2")
        self.assertIn("blob", market.polymarket_raw)
