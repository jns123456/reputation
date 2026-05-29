"""Tests for live (unrealized) reputation P&L on open forecasts."""

from django.test import TestCase

from conftest import create_market, create_user
from predictions.models import Prediction
from reputation.services import (
    calculate_unrealized_reputation,
    calculate_user_unrealized_reputation,
)


class UnrealizedReputationTests(TestCase):
    def setUp(self):
        self.user = create_user("trader")
        self.market = create_market(current_probability={"Yes": 0.30, "No": 0.70})

    def _prediction(self, *, direction=Prediction.Direction.YES, status=Prediction.Status.PENDING, entry=None):
        return Prediction.objects.create(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
            predicted_direction=direction,
            probability_at_prediction_time=entry if entry is not None else {"Yes": 0.30, "No": 0.70},
            status=status,
        )

    def test_none_for_non_open_forecast(self):
        prediction = self._prediction(status=Prediction.Status.RESOLVED)
        self.assertIsNone(calculate_unrealized_reputation(prediction))

    def test_positive_when_odds_move_in_favor(self):
        # Entered Yes at 30%; market now 55% -> +25 unrealized.
        prediction = self._prediction(entry={"Yes": 0.30, "No": 0.70})
        self.market.current_probability = {"Yes": 0.55, "No": 0.45}
        self.market.save(update_fields=["current_probability"])
        self.assertEqual(calculate_unrealized_reputation(prediction), 25)

    def test_negative_when_odds_move_against(self):
        # Entered Yes at 60%; market now 40% -> -20 unrealized.
        prediction = self._prediction(entry={"Yes": 0.60, "No": 0.40})
        self.market.current_probability = {"Yes": 0.40, "No": 0.60}
        self.market.save(update_fields=["current_probability"])
        self.assertEqual(calculate_unrealized_reputation(prediction), -20)

    def test_no_direction_inverts_sign(self):
        # Bet No at Yes=60% (i.e. No=40%); Yes drops to 40% (No=60%) -> +20.
        prediction = self._prediction(
            direction=Prediction.Direction.NO, entry={"Yes": 0.60, "No": 0.40}
        )
        self.market.current_probability = {"Yes": 0.40, "No": 0.60}
        self.market.save(update_fields=["current_probability"])
        self.assertEqual(calculate_unrealized_reputation(prediction), 20)

    def test_none_when_no_current_probability(self):
        prediction = self._prediction()
        self.market.current_probability = {}
        self.market.save(update_fields=["current_probability"])
        self.assertIsNone(calculate_unrealized_reputation(prediction))

    def test_user_total_sums_open_forecasts(self):
        self._prediction(entry={"Yes": 0.30, "No": 0.70})
        self.market.current_probability = {"Yes": 0.55, "No": 0.45}
        self.market.save(update_fields=["current_probability"])
        self.assertEqual(calculate_user_unrealized_reputation(self.user), 25)

    def test_user_total_is_zero_without_open_forecasts(self):
        prediction = self._prediction(status=Prediction.Status.RESOLVED)
        self.market.current_probability = {"Yes": 0.55, "No": 0.45}
        self.market.save(update_fields=["current_probability"])
        self.assertEqual(calculate_user_unrealized_reputation(self.user), 0)
