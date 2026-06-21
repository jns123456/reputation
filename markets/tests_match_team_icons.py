"""Tests for match team icon model properties."""

from django.test import TestCase

from markets.models import Market


class MatchTeamIconTests(TestCase):
    def test_icons_read_from_outcomes_without_raw_payload(self):
        market = Market.objects.create(
            external_id="wc-match:icon-test",
            title="Belgium vs. IR Iran",
            slug="icon-test",
            outcomes=[
                {"label": "Belgium", "icon": "https://example.com/bel.png"},
                {"label": "Draw"},
                {"label": "IR Iran", "icon": "https://example.com/irn.png"},
            ],
            polymarket_raw={"market_kind": "soccer_match_3way"},
        )
        market = Market.objects.defer("polymarket_raw", "polymarket_event_raw").get(pk=market.pk)

        self.assertEqual(market.match_team_a_icon, "https://example.com/bel.png")
        self.assertEqual(market.match_team_b_icon, "https://example.com/irn.png")

    def test_icons_fallback_to_polymarket_raw_when_outcomes_lack_icons(self):
        market = Market.objects.create(
            external_id="wc-match:icon-fallback",
            title="Belgium vs. IR Iran",
            slug="icon-fallback",
            outcomes=[{"label": "Belgium"}, {"label": "Draw"}, {"label": "IR Iran"}],
            polymarket_raw={
                "market_kind": "soccer_match_3way",
                "team_a": "Belgium",
                "team_b": "IR Iran",
                "team_a_icon": "https://example.com/bel-raw.png",
                "team_b_icon": "https://example.com/irn-raw.png",
            },
        )
        self.assertEqual(market.match_team_a_icon, "https://example.com/bel-raw.png")
        self.assertEqual(market.match_team_b_icon, "https://example.com/irn-raw.png")
