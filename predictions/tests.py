from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from accounts.selectors import get_user_prediction_history
from comments.models import Comment, Vote
from comments.services import cast_vote
from markets.models import Market
from predictions.models import Prediction
from predictions.selectors import get_market_predictions
from predictions.services import create_prediction, resolve_market_predictions, update_prediction
from predictions.forms import ForecastForm


class PredictionPermissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="pass")
        self.other = User.objects.create_user(username="other", password="pass")
        self.market = Market.objects.create(
            external_id="perm-m1",
            title="Permission test",
            slug="permission-test",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )
        self.prediction = create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
        )

    def test_other_user_cannot_edit_prediction(self):
        with self.assertRaises(PermissionError):
            update_prediction(
                prediction=self.prediction,
                user=self.other,
                predicted_outcome="No",
            )

    def test_update_prediction_is_not_allowed(self):
        with self.assertRaises(ValueError):
            update_prediction(
                prediction=self.prediction,
                user=self.user,
                predicted_outcome="No",
            )

    def test_cannot_create_duplicate_forecast(self):
        with self.assertRaises(ValueError):
            create_prediction(
                user=self.user,
                market=self.market,
                predicted_outcome="No",
            )

    def test_create_prediction_stores_probability_snapshot(self):
        self.market.current_probability = {"Yes": 0.35, "No": 0.65}
        self.market.save(update_fields=["current_probability"])
        prediction = create_prediction(
            user=self.other,
            market=self.market,
            predicted_outcome="Yes",
        )
        self.assertEqual(prediction.probability_at_prediction_time["Yes"], 0.35)
        self.assertEqual(prediction.probability_at_prediction_time["No"], 0.65)

    def test_create_prediction_stores_no_direction(self):
        prediction = create_prediction(
            user=self.other,
            market=self.market,
            predicted_outcome="Yes",
            predicted_direction=Prediction.Direction.NO,
        )

        self.assertEqual(prediction.predicted_outcome, "Yes")
        self.assertEqual(prediction.predicted_direction, Prediction.Direction.NO)

    def test_no_direction_resolves_correct_when_other_outcome_wins(self):
        prediction = create_prediction(
            user=self.other,
            market=self.market,
            predicted_outcome="Yes",
            predicted_direction=Prediction.Direction.NO,
        )
        self.market.status = Market.Status.RESOLVED
        self.market.resolved_outcome = "No"
        self.market.save(update_fields=["status", "resolved_outcome"])

        resolve_market_predictions(self.market)

        prediction.refresh_from_db()
        self.assertTrue(prediction.is_correct)

    def test_market_predictions_sorted_by_popularity(self):
        market = Market.objects.create(
            external_id="sort-m1",
            title="Sort test",
            slug="sort-test",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )
        low = create_prediction(
            user=self.user,
            market=market,
            predicted_outcome="Yes",
        )
        high = create_prediction(
            user=self.other,
            market=market,
            predicted_outcome="No",
        )
        voter = User.objects.create_user(username="voter", password="pass")
        cast_vote(
            user=voter,
            target_type=Vote.TargetType.PREDICTION,
            target_id=high.id,
            value=1,
        )
        high.refresh_from_db()

        ordered = list(get_market_predictions(market))
        self.assertEqual([prediction.id for prediction in ordered], [high.id, low.id])

    def test_market_predictions_tiebreak_by_author_reputation(self):
        market = Market.objects.create(
            external_id="sort-m2",
            title="Reputation tiebreak",
            slug="reputation-tiebreak",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )
        self.user.profile.reputation_score = 80.0
        self.user.profile.save(update_fields=["reputation_score"])
        self.other.profile.reputation_score = 20.0
        self.other.profile.save(update_fields=["reputation_score"])

        low_rep = create_prediction(
            user=self.other,
            market=market,
            predicted_outcome="No",
        )
        high_rep = create_prediction(
            user=self.user,
            market=market,
            predicted_outcome="Yes",
        )

        ordered = list(get_market_predictions(market))
        self.assertEqual([prediction.id for prediction in ordered], [high_rep.id, low_rep.id])

    def test_user_prediction_history_includes_interaction_counts(self):
        voter = User.objects.create_user(username="voter2", password="pass")
        cast_vote(
            user=voter,
            target_type=Vote.TargetType.PREDICTION,
            target_id=self.prediction.id,
            value=1,
        )
        disliker = User.objects.create_user(username="disliker", password="pass")
        cast_vote(
            user=disliker,
            target_type=Vote.TargetType.PREDICTION,
            target_id=self.prediction.id,
            value=-1,
        )
        Comment.objects.create(
            user=voter,
            market=self.market,
            prediction=self.prediction,
            body="Interesting take.",
        )

        prediction = get_user_prediction_history(self.user)[0]
        self.assertEqual(prediction.comment_count, 1)
        self.assertEqual(prediction.like_count, 1)
        self.assertEqual(prediction.dislike_count, 1)


class ForecastFormTests(TestCase):
    def test_three_way_soccer_form_accepts_all_outcomes(self):
        market = Market.objects.create(
            external_id="wc-match:test",
            title="Mexico vs. South Africa",
            slug="mexico-vs-south-africa-form",
            status=Market.Status.OPEN,
            outcomes=[
                {"label": "Mexico"},
                {"label": "Draw"},
                {"label": "South Africa"},
            ],
            current_probability={"Mexico": 0.67, "Draw": 0.22, "South Africa": 0.11},
            polymarket_raw={"market_kind": "soccer_match_3way"},
        )
        form = ForecastForm(data={"predicted_outcome": "Draw"}, market=market)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["predicted_outcome"], "Draw")
        self.assertEqual(form.outcome_count, 3)

    def test_multi_outcome_form_accepts_no_direction(self):
        market = Market.objects.create(
            external_id="pm-event:test-winner",
            title="Tournament Winner",
            slug="tournament-winner-form",
            status=Market.Status.OPEN,
            outcomes=[
                {"label": "Spain"},
                {"label": "France"},
                {"label": "England"},
            ],
            current_probability={"Spain": 0.17, "France": 0.16, "England": 0.11},
            polymarket_raw={"market_kind": "polymarket_multi_outcome_event"},
        )

        form = ForecastForm(
            data={"predicted_outcome": "Spain", "predicted_direction": "no"},
            market=market,
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["predicted_direction"], "no")
