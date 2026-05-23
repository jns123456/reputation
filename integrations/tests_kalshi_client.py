from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from integrations.kalshi.client import KalshiClient, KalshiRateLimitError


class KalshiClientRateLimitTests(SimpleTestCase):
    @override_settings(KALSHI_API_MIN_INTERVAL_MS=0, KALSHI_API_MAX_RETRIES=2)
    @patch("integrations.kalshi.client.time.sleep")
    def test_retries_on_429_then_succeeds(self, mock_sleep):
        client = KalshiClient(base_url="https://example.test/v2")
        rate_limited = MagicMock()
        rate_limited.status_code = 429
        rate_limited.headers = {"Retry-After": "1"}
        ok = MagicMock()
        ok.status_code = 200
        ok.json.return_value = {"markets": [], "cursor": ""}
        client.session.get = MagicMock(side_effect=[rate_limited, ok])

        markets, cursor = client.fetch_markets(limit=10)

        self.assertEqual(markets, [])
        self.assertEqual(cursor, "")
        self.assertEqual(client.session.get.call_count, 2)
        mock_sleep.assert_called_once_with(1.0)

    @override_settings(KALSHI_API_MIN_INTERVAL_MS=0, KALSHI_API_MAX_RETRIES=1)
    @patch("integrations.kalshi.client.time.sleep")
    def test_raises_after_exhausted_retries(self, mock_sleep):
        client = KalshiClient(base_url="https://example.test/v2")
        rate_limited = MagicMock()
        rate_limited.status_code = 429
        rate_limited.headers = {}
        client.session.get = MagicMock(return_value=rate_limited)

        with self.assertRaises(KalshiRateLimitError):
            client.fetch_markets(limit=10)
