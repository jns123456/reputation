from django.contrib.auth import get_user_model
from django.test import TestCase

from integrations.polymarket.client import (
    build_polymarket_event_raw,
    grouped_submarket_resolved_yes,
    normalize_polymarket_event_record,
)
from integrations.polymarket.constants import MULTI_OUTCOME_EVENT_KIND, POLYMARKET_EVENT_EXTERNAL_PREFIX
from markets.models import Market
from predictions.models import Prediction
from predictions.services import (
    prediction_is_correct_for_resolved_market,
    repair_misscored_multi_binary_predictions,
    resolve_market_predictions,
)
from reputation.models import ReputationEvent

User = get_user_model()


def _threshold_bucket(threshold, *, yes_price, closed=False, resolved=False):
    market = {
        "id": f"btc-{threshold.replace(',', '')}",
        "question": f"Bitcoin above {threshold} on June 20?",
        "outcomes": '["Yes", "No"]',
        "groupItemTitle": threshold,
        "groupItemThreshold": int(threshold.replace(",", "")),
        "outcomePrices": f'["{yes_price}", "{1 - yes_price}"]',
        "closed": closed,
    }
    if resolved:
        market["automaticallyResolved"] = True
        market["umaResolutionStatus"] = "resolved"
        if yes_price >= 0.99:
            market["resolvedOutcome"] = "Yes"
        elif yes_price <= 0.01:
            market["resolvedOutcome"] = "No"
    return market


BITCOIN_ABOVE_RESOLVED = {
    "slug": "bitcoin-above-on-june-20-2026",
    "title": "Bitcoin above ___ on June 20?",
    "endDate": "2026-06-20T16:00:00Z",
    "markets": [
        _threshold_bucket("54,000", yes_price=1.0, closed=True, resolved=True),
        _threshold_bucket("64,000", yes_price=1.0, closed=True, resolved=True),
        _threshold_bucket("66,000", yes_price=0.0, closed=True, resolved=True),
    ],
}


class MultiBinaryResolutionTests(TestCase):
    def setUp(self):
        normalized = normalize_polymarket_event_record(BITCOIN_ABOVE_RESOLVED)
        raw = build_polymarket_event_raw(BITCOIN_ABOVE_RESOLVED, normalized=normalized)
        self.market = Market.objects.create(
            external_id=f"{POLYMARKET_EVENT_EXTERNAL_PREFIX}bitcoin-above-on-june-20-2026",
            polymarket_slug="bitcoin-above-on-june-20-2026",
            title=normalized["title"],
            slug="bitcoin-above-on-june-20-2026-test",
            source=Market.Source.POLYMARKET,
            status=Market.Status.RESOLVED,
            outcomes=normalized["outcomes"],
            current_probability=normalized["current_probability"],
            resolved_outcome=normalized["resolved_outcome"],
            polymarket_raw={**raw, "market_kind": MULTI_OUTCOME_EVENT_KIND},
            polymarket_event_raw=BITCOIN_ABOVE_RESOLVED,
        )
        self.user = User.objects.create_user(username="btc-threshold-user", password="pass")

    def test_grouped_submarket_resolved_yes_reads_per_bucket(self):
        event = BITCOIN_ABOVE_RESOLVED
        self.assertTrue(grouped_submarket_resolved_yes(event, "54,000"))
        self.assertTrue(grouped_submarket_resolved_yes(event, "64,000"))
        self.assertFalse(grouped_submarket_resolved_yes(event, "66,000"))

    def test_normalize_stores_last_yes_bucket_as_display_winner(self):
        self.assertEqual(self.market.resolved_outcome, "64,000")

    def test_yes_on_lower_threshold_scores_correct_when_multiple_yes(self):
        prediction = Prediction.objects.create(
            user=self.user,
            market=self.market,
            predicted_outcome="54,000",
            predicted_direction=Prediction.Direction.YES,
            probability_at_prediction_time={"54,000": 1.0},
        )

        resolved = resolve_market_predictions(self.market)
        prediction.refresh_from_db()
        self.user.profile.refresh_from_db()

        self.assertEqual(len(resolved), 1)
        self.assertTrue(prediction.is_correct)
        self.assertEqual(self.user.profile.reputation_points, 0)
        self.assertEqual(
            ReputationEvent.objects.get(prediction=prediction).event_type,
            ReputationEvent.EventType.CORRECT_PREDICTION,
        )

    def test_no_on_failed_threshold_scores_correct(self):
        prediction = Prediction.objects.create(
            user=self.user,
            market=self.market,
            predicted_outcome="66,000",
            predicted_direction=Prediction.Direction.NO,
            probability_at_prediction_time={"66,000": 0.0},
        )

        resolve_market_predictions(self.market)
        prediction.refresh_from_db()

        self.assertTrue(prediction.is_correct)

    def test_repair_fixes_prior_pick_one_misscore(self):
        prediction = Prediction.objects.create(
            user=self.user,
            market=self.market,
            predicted_outcome="54,000",
            predicted_direction=Prediction.Direction.YES,
            probability_at_prediction_time={"54,000": 1.0},
            status=Prediction.Status.RESOLVED,
            is_correct=False,
        )
        self.user.profile.reputation_points = -100
        self.user.profile.scored_forecast_count = 1
        self.user.profile.incorrect_prediction_count = 1
        self.user.profile.save()

        ReputationEvent.objects.create(
            user=self.user,
            prediction=prediction,
            event_type=ReputationEvent.EventType.INCORRECT_PREDICTION,
            points_delta=-100,
            reason="Prior incorrect score",
        )

        repaired = repair_misscored_multi_binary_predictions()
        prediction.refresh_from_db()
        self.user.profile.refresh_from_db()

        self.assertEqual(repaired, [prediction.id])
        self.assertTrue(prediction.is_correct)
        self.assertEqual(self.user.profile.reputation_points, 0)
        self.assertEqual(self.user.profile.correct_prediction_count, 1)
        self.assertEqual(self.user.profile.incorrect_prediction_count, 0)
        self.assertTrue(
            prediction_is_correct_for_resolved_market(self.market, prediction)
        )
