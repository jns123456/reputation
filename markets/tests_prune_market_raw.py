from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

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
)


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
