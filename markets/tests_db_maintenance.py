from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from conftest import create_market
from markets.db_maintenance import (
    collect_storage_pressure,
    maybe_vacuum_after_orphan_cleanup,
    report_storage_pressure_if_needed,
    storage_pressure_alerts,
    vacuum_markets_market,
)
from markets.models import Market
from markets.tasks import (
    check_market_storage_pressure_task,
    delete_orphan_resolved_markets_task,
    vacuum_markets_market_task,
)


class DbMaintenanceTests(TestCase):
    def _orphan(self, external_id, *, days_ago=60):
        return create_market(
            external_id=external_id,
            slug=external_id,
            status=Market.Status.RESOLVED,
            resolution_date=timezone.now() - timedelta(days=days_ago),
        )

    def test_vacuum_skips_on_sqlite(self):
        result = vacuum_markets_market(full=False)
        self.assertFalse(result["ran"])
        self.assertEqual(result["skipped_reason"], "not_postgresql")

    def test_storage_pressure_alerts_thresholds(self):
        with override_settings(
            MARKET_STORAGE_ALERT_DB_BYTES=100,
            MARKET_STORAGE_ALERT_ORPHAN_COUNT=2,
        ):
            self.assertEqual(
                storage_pressure_alerts(
                    {"database_bytes": 50, "orphan_resolved_count": 1}
                ),
                [],
            )
            alerts = storage_pressure_alerts(
                {"database_bytes": 150, "orphan_resolved_count": 5}
            )
            self.assertEqual(len(alerts), 2)

    @override_settings(
        MARKET_STORAGE_ALERT_ENABLED=True,
        MARKET_STORAGE_ALERT_DB_BYTES=1,
        MARKET_STORAGE_ALERT_ORPHAN_COUNT=1,
    )
    def test_report_storage_pressure_captures_sentry(self):
        fake_sdk = MagicMock()
        scope = MagicMock()
        fake_sdk.new_scope.return_value.__enter__.return_value = scope
        with patch.dict("sys.modules", {"sentry_sdk": fake_sdk}):
            result = report_storage_pressure_if_needed(
                {
                    "database_bytes": 10,
                    "markets_market_bytes": 5,
                    "orphan_resolved_count": 3,
                    "retention_days": 7,
                }
            )
        self.assertTrue(result["alerts"])
        fake_sdk.capture_message.assert_called_once()

    @override_settings(MARKET_VACUUM_ENABLED=True, MARKET_VACUUM_AFTER_DELETE_MIN=100)
    def test_maybe_vacuum_skips_below_threshold(self):
        result = maybe_vacuum_after_orphan_cleanup(deleted=10)
        self.assertFalse(result["ran"])
        self.assertEqual(result["skipped_reason"], "below_delete_threshold")

    def test_collect_storage_pressure_counts_orphans(self):
        self._orphan("pressure-a")
        self._orphan("pressure-b", days_ago=3)
        snap = collect_storage_pressure(retention_days=7)
        self.assertEqual(snap["orphan_resolved_count"], 1)
        self.assertEqual(snap["retention_days"], 7)

    @override_settings(
        MARKET_ORPHAN_RESOLVED_CLEANUP_ENABLED=True,
        MARKET_ORPHAN_RESOLVED_RETENTION_DAYS=7,
        MARKET_ORPHAN_RESOLVED_CLEANUP_BATCH_SIZE=2,
        MARKET_ORPHAN_RESOLVED_CLEANUP_MAX_PER_RUN=0,
        MARKET_VACUUM_AFTER_DELETE_MIN=10_000,
        MARKET_STORAGE_ALERT_ENABLED=False,
    )
    def test_orphan_task_drains_all_eligible(self):
        kept_recent = self._orphan("recent-keep", days_ago=2)
        old_ids = [
            self._orphan(f"old-drain-{i}", days_ago=30).pk for i in range(5)
        ]
        delete_orphan_resolved_markets_task()
        for pk in old_ids:
            self.assertFalse(Market.objects.filter(pk=pk).exists())
        self.assertTrue(Market.objects.filter(pk=kept_recent.pk).exists())

    @override_settings(MARKET_VACUUM_ENABLED=False)
    def test_vacuum_task_noop_when_disabled(self):
        vacuum_markets_market_task(full=True)

    @override_settings(MARKET_STORAGE_ALERT_ENABLED=False)
    def test_storage_alert_task_noop_when_disabled(self):
        check_market_storage_pressure_task()
