from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import MarketWatch
from challenges.models import Challenge, ChallengeMarket
from comments.models import Comment
from conftest import create_market, create_user
from markets.cleanup_services import (
    maybe_compact_resolved_market_raw,
    orphan_resolved_market_queryset,
    resolve_delete_target,
    run_orphan_resolved_cleanup,
)
from markets.models import Market
from markets.prune_services import PRUNED_MARKER
from markets.tasks import delete_orphan_resolved_markets_task
from predictions.models import Prediction


class OrphanResolvedCleanupTests(TestCase):
    def _resolved(self, external_id, **kwargs):
        defaults = {
            "external_id": external_id,
            "slug": external_id,
            "status": Market.Status.RESOLVED,
            "resolution_date": timezone.now() - timedelta(days=60),
            "polymarket_raw": {"description": "x" * 2000},
            "polymarket_event_raw": {"markets": [{"id": i} for i in range(20)]},
        }
        defaults.update(kwargs)
        return create_market(**defaults)

    def test_resolve_delete_target_half_of_resolved(self):
        self.assertEqual(
            resolve_delete_target(
                orphan_total=100,
                resolved_total=80,
                min_fraction_of_resolved=0.5,
            ),
            40,
        )
        self.assertEqual(
            resolve_delete_target(
                orphan_total=10,
                resolved_total=80,
                min_fraction_of_resolved=0.5,
            ),
            10,
        )

    def test_skips_markets_with_predictions_comments_watches_challenges(self):
        orphan = self._resolved("orphan-1")
        with_pred = self._resolved("with-pred")
        with_comment = self._resolved("with-comment")
        with_watch = self._resolved("with-watch")
        with_challenge = self._resolved("with-challenge")

        user = create_user("cleanup-user")
        Prediction.objects.create(
            user=user,
            market=with_pred,
            predicted_outcome="Yes",
            predicted_direction="yes",
        )
        Comment.objects.create(user=user, market=with_comment, body="hi")
        MarketWatch.objects.create(user=user, market=with_watch)
        challenge = Challenge.objects.create(creator=user, title="c")
        ChallengeMarket.objects.create(challenge=challenge, market=with_challenge)

        orphan_ids = set(
            orphan_resolved_market_queryset().values_list("pk", flat=True)
        )
        self.assertIn(orphan.pk, orphan_ids)
        self.assertNotIn(with_pred.pk, orphan_ids)
        self.assertNotIn(with_comment.pk, orphan_ids)
        self.assertNotIn(with_watch.pk, orphan_ids)
        self.assertNotIn(with_challenge.pk, orphan_ids)

    def test_deletes_half_of_resolved_orphans_fifo(self):
        older = self._resolved(
            "old-orphan",
            resolution_date=timezone.now() - timedelta(days=90),
        )
        newer = self._resolved(
            "new-orphan",
            resolution_date=timezone.now() - timedelta(days=10),
        )
        kept = self._resolved("kept-with-pred")
        user = create_user("pred-user")
        Prediction.objects.create(
            user=user,
            market=kept,
            predicted_outcome="Yes",
            predicted_direction="yes",
        )

        # 3 resolved, 2 orphans → half of resolved = 1 (floor 1)
        stats = run_orphan_resolved_cleanup(
            min_fraction_of_resolved=0.5,
            dry_run=False,
        )
        self.assertEqual(stats["deleted"], 1)
        self.assertFalse(Market.objects.filter(pk=older.pk).exists())
        self.assertTrue(Market.objects.filter(pk=newer.pk).exists())
        self.assertTrue(Market.objects.filter(pk=kept.pk).exists())

    def test_retention_days_filters_recent_orphans(self):
        old = self._resolved(
            "old-ret",
            resolution_date=timezone.now() - timedelta(days=40),
        )
        recent = self._resolved(
            "recent-ret",
            resolution_date=timezone.now() - timedelta(days=5),
        )
        stats = run_orphan_resolved_cleanup(older_than_days=30, dry_run=False)
        self.assertEqual(stats["deleted"], 1)
        self.assertFalse(Market.objects.filter(pk=old.pk).exists())
        self.assertTrue(Market.objects.filter(pk=recent.pk).exists())

    def test_dry_run_does_not_delete(self):
        market = self._resolved("dry-run-orphan")
        stats = run_orphan_resolved_cleanup(dry_run=True)
        self.assertEqual(stats["deleted"], 1)
        self.assertTrue(Market.objects.filter(pk=market.pk).exists())

    def test_management_command_dry_run(self):
        self._resolved("cmd-orphan")
        out = StringIO()
        call_command(
            "delete_orphan_resolved_markets",
            "--dry-run",
            "--min-fraction-of-resolved",
            "0.5",
            stdout=out,
        )
        self.assertIn("Would delete", out.getvalue())

    @override_settings(
        MARKET_ORPHAN_RESOLVED_CLEANUP_ENABLED=True,
        MARKET_ORPHAN_RESOLVED_RETENTION_DAYS=30,
        MARKET_ORPHAN_RESOLVED_CLEANUP_BATCH_SIZE=10,
    )
    def test_celery_task_respects_retention(self):
        old = self._resolved(
            "task-old",
            resolution_date=timezone.now() - timedelta(days=45),
        )
        delete_orphan_resolved_markets_task()
        self.assertFalse(Market.objects.filter(pk=old.pk).exists())

    @override_settings(MARKET_ORPHAN_RESOLVED_CLEANUP_ENABLED=False)
    def test_celery_task_noop_when_disabled(self):
        market = self._resolved(
            "task-disabled",
            resolution_date=timezone.now() - timedelta(days=45),
        )
        delete_orphan_resolved_markets_task()
        self.assertTrue(Market.objects.filter(pk=market.pk).exists())

    def test_maybe_compact_resolved_market_raw(self):
        market = self._resolved("compact-me")
        self.assertTrue(maybe_compact_resolved_market_raw(market))
        market.refresh_from_db()
        self.assertIn(PRUNED_MARKER, market.polymarket_raw)
        self.assertIn(PRUNED_MARKER, market.polymarket_event_raw)
        self.assertFalse(maybe_compact_resolved_market_raw(market))
