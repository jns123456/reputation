import time
from unittest.mock import patch

from django.core.cache import cache
from django.db import OperationalError
from django.test import SimpleTestCase, override_settings

from integrations.market_sync_scheduler import (
    FULL_SYNC_LOCK_KEY,
    LAST_FULL_SYNC_KEY,
    LAST_STALE_SYNC_KEY,
    STALE_SYNC_LOCK_KEY,
    _is_transient_db_error,
    _log_sync_loop_failure,
    is_full_sync_due,
    is_stale_sync_due,
    run_stale_market_refresh,
    run_scheduled_market_sync,
)


@override_settings(MARKET_FULL_SYNC_INTERVAL_HOURS=6)
class MarketSyncSchedulerTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_is_full_sync_due_when_never_run(self):
        self.assertTrue(is_full_sync_due())

    def test_is_full_sync_due_false_after_recent_run(self):
        cache.set(LAST_FULL_SYNC_KEY, time.time(), timeout=None)
        self.assertFalse(is_full_sync_due())

    def test_is_stale_sync_due_false_after_recent_run(self):
        cache.set(LAST_STALE_SYNC_KEY, time.time(), timeout=None)
        self.assertFalse(is_stale_sync_due())

    @patch("integrations.market_sync_scheduler.time.time")
    def test_is_full_sync_due_true_after_interval(self, mock_time):
        now = 1_700_000_000.0
        mock_time.return_value = now
        cache.set(LAST_FULL_SYNC_KEY, now - (6 * 3600), timeout=None)
        self.assertTrue(is_full_sync_due())

    @patch("integrations.sync.refresh_stale_open_markets")
    @patch("integrations.sync.sync_all_category_markets")
    def test_run_scheduled_market_sync_skips_when_not_due(self, mock_sync, mock_stale):
        cache.set(LAST_FULL_SYNC_KEY, time.time(), timeout=None)
        cache.set(LAST_STALE_SYNC_KEY, time.time(), timeout=None)
        self.assertIsNone(run_scheduled_market_sync())
        mock_sync.assert_not_called()
        mock_stale.assert_not_called()

    @patch("integrations.sync.refresh_stale_open_markets")
    @patch("integrations.sync.sync_all_category_markets")
    def test_run_scheduled_market_sync_runs_when_due(self, mock_sync, mock_stale):
        mock_sync.return_value = {"imported": 2, "updated": 1, "errors": []}
        mock_stale.return_value = {"refreshed": 3, "failures": 0, "candidates": 3}

        result = run_scheduled_market_sync(force=True)

        self.assertIsNotNone(result)
        mock_sync.assert_called_once()
        mock_stale.assert_called_once()
        self.assertFalse(is_full_sync_due())
        self.assertIsNone(cache.get(FULL_SYNC_LOCK_KEY))

    @patch("integrations.sync.refresh_stale_open_markets")
    @patch("integrations.sync.sync_all_category_markets")
    def test_run_scheduled_market_sync_can_run_only_stale_refresh(self, mock_sync, mock_stale):
        cache.set(LAST_FULL_SYNC_KEY, time.time(), timeout=None)
        mock_stale.return_value = {"refreshed": 2, "failures": 0, "candidates": 2}

        result = run_scheduled_market_sync()

        self.assertIsNotNone(result)
        self.assertIsNone(result["categories"])
        self.assertEqual(result["stale"]["refreshed"], 2)
        mock_sync.assert_not_called()
        mock_stale.assert_called_once()

    @patch("integrations.sync.refresh_stale_open_markets")
    def test_run_stale_market_refresh_records_and_unlocks(self, mock_stale):
        mock_stale.return_value = {"refreshed": 1, "failures": 0, "candidates": 1}

        result = run_stale_market_refresh(force=True)

        self.assertEqual(result["refreshed"], 1)
        self.assertFalse(is_stale_sync_due())
        self.assertIsNone(cache.get(STALE_SYNC_LOCK_KEY))

    def test_is_transient_db_error_detects_ssl_eof(self):
        exc = OperationalError("consuming input failed: SSL error: unexpected eof while reading")
        self.assertTrue(_is_transient_db_error(exc))

    def test_is_transient_db_error_rejects_other_operational_errors(self):
        exc = OperationalError("duplicate key value violates unique constraint")
        self.assertFalse(_is_transient_db_error(exc))

    @patch("integrations.market_sync_scheduler.logger")
    def test_log_sync_loop_failure_downgrades_transient_db_errors(self, mock_logger):
        exc = OperationalError("SSL error: unexpected eof while reading")
        _log_sync_loop_failure(exc)
        mock_logger.warning.assert_called_once()
        mock_logger.exception.assert_not_called()

    @patch("integrations.market_sync_scheduler.logger")
    def test_log_sync_loop_failure_keeps_exception_for_other_errors(self, mock_logger):
        _log_sync_loop_failure(RuntimeError("boom"))
        mock_logger.exception.assert_called_once_with("Embedded market sync loop failed")
        mock_logger.warning.assert_not_called()
