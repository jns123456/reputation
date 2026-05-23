from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from integrations.celery_utils import celery_broker_available, enqueue_category_sync


class CeleryBrokerAvailabilityTests(SimpleTestCase):
    @override_settings(CELERY_BROKER_URL="redis://127.0.0.1:6399/0")
    def test_celery_broker_available_false_when_unreachable(self):
        with patch("integrations.celery_utils.cache") as mock_cache:
            mock_cache.get.return_value = None
            self.assertFalse(celery_broker_available(force_check=True))

    @patch("integrations.celery_utils.celery_broker_available", return_value=False)
    def test_enqueue_skips_when_broker_unavailable(self, _mock_available):
        self.assertFalse(enqueue_category_sync("economy"))
