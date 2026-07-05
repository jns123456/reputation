"""Resolution scorecard on market detail pages."""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from conftest import create_market, create_user
from markets.models import Market
from predictions.selectors import get_market_resolution_scorecard
from predictions.services import create_prediction, resolve_market_predictions


class MarketResolutionScorecardSelectorTests(TestCase):
    def setUp(self):
        self.market = create_market(
            external_id="scorecard-m1",
            slug="scorecard-market",
            current_probability={"Yes": 0.7, "No": 0.3},
        )
        self.winner = create_user("winner")
        self.loser = create_user("loser")
        self.contrarian = create_user("contrarian")

    def _resolve_yes(self):
        self.market.status = Market.Status.RESOLVED
        self.market.resolved_outcome = "Yes"
        self.market.resolution_date = timezone.now()
        self.market.save(update_fields=["status", "resolved_outcome", "resolution_date"])

    def test_returns_none_for_open_market(self):
        self.assertIsNone(get_market_resolution_scorecard(self.market))

    def test_aggregates_accuracy_and_top_performers(self):
        create_prediction(
            user=self.winner,
            market=self.market,
            predicted_outcome="Yes",
        )
        create_prediction(
            user=self.loser,
            market=self.market,
            predicted_outcome="No",
        )
        self._resolve_yes()
        resolve_market_predictions(self.market)

        scorecard = get_market_resolution_scorecard(self.market)

        self.assertTrue(scorecard["has_scored_forecasts"])
        self.assertEqual(scorecard["scored_count"], 2)
        self.assertEqual(scorecard["correct_count"], 1)
        self.assertEqual(scorecard["incorrect_count"], 1)
        self.assertEqual(scorecard["accuracy_pct"], 50)
        self.assertEqual(scorecard["top_performers"][0]["user"], self.winner)
        self.assertGreater(scorecard["top_performers"][0]["points_delta"], 0)
        self.assertEqual(len(scorecard["biggest_wins"]), 1)
        self.assertEqual(len(scorecard["biggest_losses"]), 1)

    def test_highlights_contrarian_correct_forecast(self):
        contrarian_market = create_market(
            external_id="scorecard-m2",
            slug="contrarian-market",
            current_probability={"Yes": 0.2, "No": 0.8},
        )
        create_prediction(
            user=self.contrarian,
            market=contrarian_market,
            predicted_outcome="Yes",
        )
        contrarian_market.status = Market.Status.RESOLVED
        contrarian_market.resolved_outcome = "Yes"
        contrarian_market.save(update_fields=["status", "resolved_outcome"])
        resolve_market_predictions(contrarian_market)

        scorecard = get_market_resolution_scorecard(contrarian_market)

        self.assertEqual(len(scorecard["contrarian_winners"]), 1)
        self.assertEqual(scorecard["contrarian_winners"][0]["user"], self.contrarian)
        self.assertLessEqual(scorecard["contrarian_winners"][0]["entry_prob_percent"], 25)


class MarketResolutionScorecardViewTests(TestCase):
    def setUp(self):
        self.market = create_market(
            external_id="scorecard-view",
            slug="scorecard-view-market",
            current_probability={"Yes": 0.6, "No": 0.4},
        )
        self.user = create_user("viewer")
        create_prediction(user=self.user, market=self.market, predicted_outcome="Yes")
        self.market.status = Market.Status.RESOLVED
        self.market.resolved_outcome = "Yes"
        self.market.save(update_fields=["status", "resolved_outcome"])
        resolve_market_predictions(self.market)

    def test_market_detail_renders_scorecard(self):
        response = self.client.get(
            reverse("markets:detail", kwargs={"slug": self.market.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Resolution scorecard")
        self.assertContains(response, "Community accuracy")
        self.assertContains(response, "Top performers")
        self.assertContains(response, self.user.public_name)

    def test_market_detail_scorecard_renders_spanish(self):
        response = self.client.get(
            reverse("markets:detail", kwargs={"slug": self.market.slug}),
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cuadro de resolución")
        self.assertContains(response, "Precisión de la comunidad")

    def test_open_market_hides_scorecard(self):
        open_market = create_market(
            external_id="open-view",
            slug="open-view-market",
        )
        response = self.client.get(
            reverse("markets:detail", kwargs={"slug": open_market.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Resolution scorecard")
