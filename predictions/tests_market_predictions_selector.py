from django.test import TestCase

from conftest import create_user
from markets.models import Market
from predictions.selectors import get_market_predictions
from predictions.services import create_prediction


class MarketPredictionsSelectorTests(TestCase):
    def setUp(self):
        self.user = create_user(username="selector-owner")

    def test_get_market_predictions_respects_limit(self):
        market = Market.objects.create(
            external_id="sort-m3",
            title="Limit test",
            slug="limit-test",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )
        for idx in range(12):
            user = create_user(username=f"limit-user-{idx}")
            create_prediction(
                user=user,
                market=market,
                predicted_outcome="Yes" if idx % 2 else "No",
            )

        ordered = list(get_market_predictions(market, limit=5))
        self.assertEqual(len(ordered), 5)

    def test_get_market_predictions_can_skip_interaction_annotations(self):
        market = Market.objects.create(
            external_id="sort-m4",
            title="Lean test",
            slug="lean-test",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )
        create_prediction(user=self.user, market=market, predicted_outcome="Yes")

        lean_qs = get_market_predictions(market, with_interactions=False)
        self.assertNotIn("like_count", lean_qs.query.annotations)
        self.assertNotIn("comment_count", lean_qs.query.annotations)

        full_qs = get_market_predictions(market, with_interactions=True)
        self.assertIn("like_count", full_qs.query.annotations)
        self.assertIn("comment_count", full_qs.query.annotations)
