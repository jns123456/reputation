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

    @patch("integrations.polymarket.client.time.sleep")
    def test_fetch_event_by_slug_retries_transient_500(self, mock_sleep):
        error_response = MagicMock()
        error_response.status_code = 500
        ok_response = MagicMock()
        ok_response.status_code = 200
        ok_response.json.return_value = {"slug": "demo-event"}

        self.client.session.get = MagicMock(side_effect=[error_response, ok_response])

        event = self.client.fetch_event_by_slug("demo-event")

        self.assertEqual(event["slug"], "demo-event")
        self.assertEqual(self.client.session.get.call_count, 2)
        mock_sleep.assert_called_once_with(1)

    @patch("integrations.polymarket.client.time.sleep")
    def test_fetch_event_by_slug_returns_none_after_persistent_500(self, mock_sleep):
        error_response = MagicMock()
        error_response.status_code = 500

        self.client.session.get = MagicMock(return_value=error_response)

        with self.assertLogs("integrations.polymarket.client", level="WARNING") as logs:
            event = self.client.fetch_event_by_slug("demo-event")

        self.assertIsNone(event)
        self.assertEqual(self.client.session.get.call_count, 3)
        self.assertTrue(any("unavailable (HTTP 500)" in msg for msg in logs.output))

    @patch("integrations.polymarket.client.time.sleep")
    def test_fetch_events_retries_transient_timeout(self, mock_sleep):
        ok_response = MagicMock()
        ok_response.status_code = 200
        ok_response.json.return_value = [{"slug": "demo-event"}]

        self.client.session.get = MagicMock(
            side_effect=[
                requests.exceptions.ReadTimeout("read timed out"),
                ok_response,
            ]
        )

        events = self.client.fetch_events(tag_slug="mlb", limit=100, offset=100)

        self.assertEqual(events[0]["slug"], "demo-event")
        self.assertEqual(self.client.session.get.call_count, 2)
        mock_sleep.assert_called_once_with(1)

    @patch("integrations.polymarket.client.time.sleep")
    def test_fetch_markets_retries_transient_timeout(self, mock_sleep):
        ok_response = MagicMock()
        ok_response.status_code = 200
        ok_response.json.return_value = [{"id": "market-1"}]

        self.client.session.get = MagicMock(
            side_effect=[
                requests.exceptions.ReadTimeout("read timed out"),
                ok_response,
            ]
        )

        markets = self.client.fetch_markets(limit=20, active=True, closed=False)

        self.assertEqual(markets[0]["id"], "market-1")
        self.assertEqual(self.client.session.get.call_count, 2)
        mock_sleep.assert_called_once_with(1)
