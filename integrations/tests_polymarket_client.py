from unittest.mock import MagicMock, patch

import requests
from django.test import SimpleTestCase

from integrations.polymarket.client import PolymarketClient


class PolymarketClientRetryTests(SimpleTestCase):
    def setUp(self):
        self.client = PolymarketClient(base_url="https://gamma-api.polymarket.com")

    @patch("integrations.polymarket.client.time.sleep")
    def test_fetch_event_by_slug_retries_transient_timeout(self, mock_sleep):
        ok_response = MagicMock()
        ok_response.status_code = 200
        ok_response.json.return_value = {"slug": "demo-event"}

        self.client.session.get = MagicMock(
            side_effect=[
                requests.exceptions.ReadTimeout("read timed out"),
                ok_response,
            ]
        )

        event = self.client.fetch_event_by_slug("demo-event")

        self.assertEqual(event["slug"], "demo-event")
        self.assertEqual(self.client.session.get.call_count, 2)
        mock_sleep.assert_called_once_with(1)

    @patch("integrations.polymarket.client.time.sleep")
    def test_fetch_event_by_slug_raises_after_retry_exhaustion(self, mock_sleep):
        self.client.session.get = MagicMock(
            side_effect=requests.exceptions.ReadTimeout("read timed out")
        )

        with self.assertRaises(requests.exceptions.ReadTimeout):
            self.client.fetch_event_by_slug("demo-event")

        self.assertEqual(self.client.session.get.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)
