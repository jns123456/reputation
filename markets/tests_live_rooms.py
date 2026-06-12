"""Live event rooms: live-mode detection, comment stream, slow mode."""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from conftest import create_market, create_user
from markets.live_rooms import enforce_live_slow_mode, is_live_room


class LiveRoomTests(TestCase):
    def _live_market(self, **kwargs):
        defaults = {
            "external_id": "live-m",
            "slug": "live-m",
            "close_date": timezone.now() + timedelta(hours=2),
        }
        defaults.update(kwargs)
        return create_market(**defaults)

    def test_market_closing_soon_is_live(self):
        self.assertTrue(is_live_room(self._live_market()))

    def test_market_closing_far_out_is_not_live(self):
        market = self._live_market(
            external_id="far-m",
            slug="far-m",
            close_date=timezone.now() + timedelta(days=10),
        )
        self.assertFalse(is_live_room(market))

    def test_closed_market_is_not_live(self):
        from markets.models import Market

        market = self._live_market(
            external_id="closed-m",
            slug="closed-m",
            status=Market.Status.CLOSED,
        )
        self.assertFalse(is_live_room(market))

    def test_slow_mode_blocks_rapid_comments(self):
        market = self._live_market(external_id="slow-m", slug="slow-m")
        user = create_user("slowmode")
        enforce_live_slow_mode(user=user, market=market)
        with self.assertRaises(ValueError):
            enforce_live_slow_mode(user=user, market=market)

    def test_live_stream_endpoint_renders(self):
        market = self._live_market(external_id="stream-m", slug="stream-m")
        response = self.client.get(
            reverse("markets:live_stream", kwargs={"slug": market.slug})
        )
        self.assertEqual(response.status_code, 200)

    def test_live_room_section_on_market_detail(self):
        market = self._live_market(external_id="detail-m", slug="detail-m")
        response = self.client.get(
            reverse("markets:detail", kwargs={"slug": market.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "live-room")
