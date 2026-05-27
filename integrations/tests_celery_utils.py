from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from integrations.celery_utils import (
    celery_broker_available,
    enqueue_category_sync,
    enqueue_market_refresh_if_stale,
    market_is_stale,
)


class CeleryBrokerAvailabilityTests(SimpleTestCase):
    @override_settings(CELERY_BROKER_URL="redis://127.0.0.1:6399/0")
    def test_celery_broker_available_false_when_unreachable(self):
        with patch("integrations.celery_utils.cache") as mock_cache:
            mock_cache.get.return_value = None
            self.assertFalse(celery_broker_available(force_check=True))

    @patch("integrations.celery_utils.celery_broker_available", return_value=False)
    def test_enqueue_skips_when_broker_unavailable(self, _mock_available):
        self.assertFalse(enqueue_category_sync("economy"))


class MarketRefreshEnqueueTests(SimpleTestCase):
    def test_market_is_stale_when_never_synced(self):
        market = MagicMock()
        market.source = "polymarket"
        market.status = "open"
        market.polymarket_synced_at = None
        market.kalshi_synced_at = None
        self.assertTrue(market_is_stale(market))

    def test_market_is_not_stale_when_recently_synced(self):
        market = MagicMock()
        market.source = "polymarket"
        market.status = "open"
        market.polymarket_synced_at = timezone.now()
        self.assertFalse(market_is_stale(market))

    @patch("integrations.celery_utils.cache")
    @patch("integrations.celery_utils.celery_broker_available", return_value=True)
    @patch("integrations.tasks.refresh_market_task")
    def test_enqueue_market_refresh_if_stale(self, mock_task, _mock_broker, mock_cache):
        mock_cache.get.return_value = None
        market = MagicMock()
        market.pk = 42
        market.source = "polymarket"
        market.status = "open"
        market.polymarket_synced_at = None

        self.assertTrue(enqueue_market_refresh_if_stale(market))
        mock_task.delay.assert_called_once_with(42)
        mock_cache.set.assert_called_once()
