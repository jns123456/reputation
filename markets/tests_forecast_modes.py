from django.test import SimpleTestCase, TestCase

from integrations.polymarket.constants import MULTI_OUTCOME_EVENT_KIND
from markets.forecast_modes import ForecastMode, get_forecast_mode
from markets.models import Market


class ForecastModeTests(SimpleTestCase):
    def _market(self, **kwargs):
        return Market(**kwargs)

    def test_binary_market(self):
        market = self._market(
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            polymarket_raw={},
        )
        self.assertEqual(get_forecast_mode(market), ForecastMode.BINARY)

    def test_soccer_match_is_pick_one(self):
        market = self._market(
            outcomes=[{"label": "Colombia"}, {"label": "Draw"}, {"label": "Costa Rica"}],
            polymarket_raw={"market_kind": "soccer_match_3way"},
        )
        self.assertEqual(get_forecast_mode(market), ForecastMode.PICK_ONE)

    def test_grouped_event_is_multi_binary(self):
        market = self._market(
            outcomes=[{"label": "Alice"}, {"label": "Bob"}, {"label": "Carol"}],
            polymarket_raw={"market_kind": MULTI_OUTCOME_EVENT_KIND},
        )
        self.assertEqual(get_forecast_mode(market), ForecastMode.MULTI_BINARY)

    def test_unknown_three_outcome_defaults_pick_one(self):
        market = self._market(
            outcomes=[{"label": "A"}, {"label": "B"}, {"label": "C"}],
            polymarket_raw={},
        )
        self.assertEqual(get_forecast_mode(market), ForecastMode.PICK_ONE)


class ForecastModeFilterTests(TestCase):
    def test_deferred_event_market_does_not_fetch_raw_payload(self):
        market = Market.objects.create(
            external_id="pm-event:test-winner",
            title="Winner",
            slug="winner",
            outcomes=[{"label": "Alice"}, {"label": "Bob"}],
            polymarket_raw={"market_kind": MULTI_OUTCOME_EVENT_KIND},
        )
        market = Market.objects.defer("polymarket_raw", "polymarket_event_raw").get(pk=market.pk)

        with self.assertNumQueries(0):
            mode = get_forecast_mode(market)

        self.assertEqual(mode, ForecastMode.MULTI_BINARY)

    def test_deferred_world_cup_match_does_not_fetch_raw_payload(self):
        market = Market.objects.create(
            external_id="wc-match:test-match",
            title="A vs B",
            slug="test-match",
            outcomes=[{"label": "A"}, {"label": "Draw"}, {"label": "B"}],
            polymarket_raw={"market_kind": "soccer_match_3way"},
        )
        market = Market.objects.defer("polymarket_raw", "polymarket_event_raw").get(pk=market.pk)

        with self.assertNumQueries(0):
            mode = get_forecast_mode(market)

        self.assertEqual(mode, ForecastMode.PICK_ONE)

    def test_is_multi_outcome_filter_matches_multi_binary_only(self):
        from dashboard.templatetags.reputation_filters import is_multi_outcome_market, is_pick_one_market

        soccer = Market.objects.create(
            external_id="mode-soccer",
            title="A vs B",
            slug="mode-soccer",
            outcomes=[{"label": "A"}, {"label": "Draw"}, {"label": "B"}],
            polymarket_raw={"market_kind": "soccer_match_3way"},
        )
        grouped = Market.objects.create(
            external_id="mode-grouped",
            title="Nominee",
            slug="mode-grouped",
            outcomes=[{"label": "Alice"}, {"label": "Bob"}],
            polymarket_raw={"market_kind": MULTI_OUTCOME_EVENT_KIND},
        )

        self.assertFalse(is_multi_outcome_market(soccer))
        self.assertTrue(is_pick_one_market(soccer))
        self.assertTrue(is_multi_outcome_market(grouped))
        self.assertFalse(is_pick_one_market(grouped))
