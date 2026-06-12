from django.test import TestCase

from accounts.models import User
from comments.models import Vote
from comments.services import cast_vote, create_comment
from markets.models import Market
from predictions.models import Prediction
from predictions.services import create_prediction, resolve_market_predictions
from reputation.models import PopularityEvent, ReputationEvent
from reputation.services import (
    calculate_exit_reputation_delta,
    calculate_reputation_delta,
    calculate_reputation_score,
    calculate_reputation_stakes,
)


class ReputationRankingModeTests(TestCase):
    def setUp(self):
        from accounts.models import UserProfile

        self.high_volume = User.objects.create_user(username="volume", password="pass")
        self.high_avg = User.objects.create_user(username="quality", password="pass")
        self.unqualified = User.objects.create_user(username="newbie", password="pass")

        UserProfile.objects.filter(user=self.high_volume).update(
            reputation_points=300,
            scored_forecast_count=15,
            reputation_score=20.0,
        )
        UserProfile.objects.filter(user=self.high_avg).update(
            reputation_points=120,
            scored_forecast_count=12,
            reputation_score=40.0,
        )
        UserProfile.objects.filter(user=self.unqualified).update(
            reputation_points=80,
            scored_forecast_count=5,
            reputation_score=80.0,
        )

    def test_absolute_ranking_orders_by_total_points(self):
        from accounts.selectors import get_top_predictors
        from reputation.ranking_modes import ABSOLUTE

        leaders = list(get_top_predictors(10, mode=ABSOLUTE))
        self.assertEqual(leaders[0].user.username, "volume")

    def test_relative_ranking_orders_qualified_by_average(self):
        from accounts.selectors import get_top_predictors
        from reputation.ranking_modes import RELATIVE

        leaders = list(get_top_predictors(10, mode=RELATIVE))
        self.assertEqual(leaders[0].user.username, "quality")
        self.assertEqual(leaders[1].user.username, "volume")

    def test_relative_ranking_lists_unqualified_after_qualified(self):
        from accounts.selectors import get_top_predictors
        from reputation.leaderboard import build_leaderboard_rows
        from reputation.ranking_modes import RELATIVE

        leaders = list(get_top_predictors(10, mode=RELATIVE))
        usernames = [row.user.username for row in leaders]
        self.assertIn("newbie", usernames)
        self.assertGreater(usernames.index("newbie"), usernames.index("quality"))

        rows = build_leaderboard_rows(leaders, ranking_mode=RELATIVE)
        newbie_row = next(row for row in rows if row["stats"].user.username == "newbie")
        self.assertIsNone(newbie_row["rank"])
        self.assertFalse(newbie_row["qualifies_relative"])

    def test_qualifies_for_relative_ranking_requires_more_than_min(self):
        from reputation.ranking_modes import qualifies_for_relative_ranking

        self.assertFalse(qualifies_for_relative_ranking(10))
        self.assertTrue(qualifies_for_relative_ranking(11))


class ReputationScoreTests(TestCase):
    def test_average_with_min_sample_penalty(self):
        self.assertEqual(
            calculate_reputation_score(reputation_points=60, scored_forecast_count=1),
            20.0,
        )
        self.assertEqual(
            calculate_reputation_score(reputation_points=120, scored_forecast_count=2),
            40.0,
        )

    def test_average_uses_true_count_at_or_above_min_sample(self):
        self.assertEqual(
            calculate_reputation_score(reputation_points=180, scored_forecast_count=3),
            60.0,
        )
        self.assertEqual(
            calculate_reputation_score(reputation_points=500, scored_forecast_count=10),
            50.0,
        )

    def test_zero_scored_forecasts(self):
        self.assertEqual(
            calculate_reputation_score(reputation_points=100, scored_forecast_count=0),
            0.0,
        )


class ReputationScoringTests(TestCase):
    def test_stakes_at_ninety_percent(self):
        """User example: 90% market → +10 if correct, −90 if wrong."""
        stakes = calculate_reputation_stakes(
            predicted_outcome="Yes",
            probability_snapshot={"Yes": 0.9, "No": 0.1},
        )
        self.assertEqual(stakes["prob_percent"], 90)
        self.assertEqual(stakes["win_points"], 10)
        self.assertEqual(stakes["loss_points"], 90)

        self.assertEqual(
            calculate_reputation_delta(
                is_correct=True,
                predicted_outcome="Yes",
                probability_snapshot={"Yes": 0.9, "No": 0.1},
            ),
            10,
        )
        self.assertEqual(
            calculate_reputation_delta(
                is_correct=False,
                predicted_outcome="Yes",
                probability_snapshot={"Yes": 0.9, "No": 0.1},
            ),
            -90,
        )

    def test_stakes_at_ten_percent_contrarian(self):
        stakes = calculate_reputation_stakes(
            predicted_outcome="Yes",
            probability_snapshot={"Yes": 0.1, "No": 0.9},
        )
        self.assertEqual(stakes["win_points"], 90)
        self.assertEqual(stakes["loss_points"], 10)

    def test_stakes_at_fifty_percent(self):
        stakes = calculate_reputation_stakes(
            predicted_outcome="Yes",
            probability_snapshot={"Yes": 0.5, "No": 0.5},
        )
        self.assertEqual(stakes["win_points"], 50)
        self.assertEqual(stakes["loss_points"], 50)

    def test_exit_delta_uses_percentage_point_difference(self):
        self.assertEqual(
            calculate_exit_reputation_delta(
                predicted_outcome="Yes",
                entry_probability_snapshot={"Yes": 0.4, "No": 0.6},
                exit_probability_snapshot={"Yes": 0.55, "No": 0.45},
            ),
            15,
        )

    def test_exit_delta_respects_no_direction(self):
        self.assertEqual(
            calculate_exit_reputation_delta(
                predicted_outcome="Yes",
                predicted_direction=Prediction.Direction.NO,
                entry_probability_snapshot={"Yes": 0.4, "No": 0.6},
                exit_probability_snapshot={"Yes": 0.7, "No": 0.3},
            ),
            -30,
        )


class PopularityReputationSeparationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="pass")
        self.other = User.objects.create_user(username="bob", password="pass")
        self.market = Market.objects.create(
            external_id="m1",
            title="Test",
            slug="test",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )

    def test_vote_affects_popularity_not_reputation(self):
        comment = create_comment(user=self.user, market=self.market, body="Hello")
        initial_rep = self.user.profile.reputation_points
        cast_vote(
            user=self.other,
            target_type=Vote.TargetType.COMMENT,
            target_id=comment.id,
            value=1,
        )
        self.user.profile.refresh_from_db()
        self.assertGreater(self.user.profile.popularity_points, 0)
        self.assertEqual(self.user.profile.reputation_points, initial_rep)
        self.assertTrue(PopularityEvent.objects.filter(user=self.user).exists())
        self.assertFalse(ReputationEvent.objects.filter(user=self.user).exists())

    def test_prediction_vote_affects_popularity_not_reputation(self):
        forecast = create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
        )
        initial_rep = self.user.profile.reputation_points
        cast_vote(
            user=self.other,
            target_type=Vote.TargetType.PREDICTION,
            target_id=forecast.id,
            value=1,
        )
        forecast.refresh_from_db()
        self.user.profile.refresh_from_db()
        self.assertGreater(forecast.popularity_score, 0)
        self.assertGreater(self.user.profile.popularity_points, 0)
        self.assertEqual(self.user.profile.reputation_points, initial_rep)


class PredictionResolutionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="carol", password="pass")
        self.market = Market.objects.create(
            external_id="m2",
            title="Resolved market",
            slug="resolved-market",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.4, "No": 0.6},
            resolved_outcome="",
        )
        self.prediction = create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
        )

    def test_resolve_correct_prediction(self):
        self.market.status = Market.Status.RESOLVED
        self.market.resolved_outcome = "Yes"
        self.market.save()
        resolve_market_predictions(self.market)
        self.prediction.refresh_from_db()
        self.user.profile.refresh_from_db()
        self.assertEqual(self.prediction.status, Prediction.Status.RESOLVED)
        self.assertTrue(self.prediction.is_correct)
        self.assertEqual(self.user.profile.reputation_points, 60)
        self.assertEqual(self.user.profile.scored_forecast_count, 1)
        self.assertEqual(self.user.profile.reputation_score, 20.0)
        event = ReputationEvent.objects.get(user=self.user)
        self.assertEqual(event.points_delta, 60)

    def test_resolve_incorrect_prediction(self):
        self.market.status = Market.Status.RESOLVED
        self.market.resolved_outcome = "No"
        self.market.save()
        resolve_market_predictions(self.market)
        self.prediction.refresh_from_db()
        self.user.profile.refresh_from_db()
        self.assertFalse(self.prediction.is_correct)
        self.assertEqual(self.user.profile.reputation_points, -40)
        self.assertEqual(self.user.profile.scored_forecast_count, 1)
        self.assertAlmostEqual(self.user.profile.reputation_score, -13.33)
        event = ReputationEvent.objects.get(user=self.user)
        self.assertEqual(event.points_delta, -40)

    def test_resolved_predictions_not_deletable_via_service(self):
        self.market.status = Market.Status.RESOLVED
        self.market.resolved_outcome = "No"
        self.market.save()
        resolve_market_predictions(self.market)
        self.prediction.refresh_from_db()
        self.assertFalse(self.prediction.is_correct)
        with self.assertRaises(ValueError):
            from predictions.services import update_prediction

            update_prediction(
                prediction=self.prediction,
                user=self.user,
                predicted_outcome="No",
            )


class PredictionExitReputationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="exit-stats", password="pass")
        self.market = Market.objects.create(
            external_id="exit-stats-m1",
            title="Exit stats market",
            slug="exit-stats-market",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.4, "No": 0.6},
        )

    def test_exit_updates_leaderboard_accuracy_counters(self):
        from dashboard.templatetags.reputation_filters import resolved_forecast_accuracy
        from predictions.services import exit_prediction

        prediction = create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
        )
        self.market.current_probability = {"Yes": 0.55, "No": 0.45}
        self.market.save(update_fields=["current_probability"])
        exit_prediction(prediction=prediction, user=self.user)

        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.scored_forecast_count, 1)
        self.assertEqual(self.user.profile.correct_prediction_count, 1)
        self.assertEqual(self.user.profile.incorrect_prediction_count, 0)
        self.assertEqual(resolved_forecast_accuracy(self.user.profile), 100)


class MarketImportNormalizationTests(TestCase):
    def test_normalize_polymarket_record(self):
        from integrations.polymarket.client import normalize_polymarket_record

        raw = {
            "id": "12345",
            "question": "Will X happen?",
            "description": "A test market",
            "category": "Politics",
            "closed": False,
            "resolved": False,
            "tokens": [
                {"outcome": "Yes", "price": 0.65},
                {"outcome": "No", "price": 0.35},
            ],
        }
        data = normalize_polymarket_record(raw)
        self.assertEqual(data["external_id"], "12345")
        self.assertEqual(data["title"], "Will X happen?")
        self.assertEqual(data["status"], "open")
        self.assertEqual(len(data["outcomes"]), 2)
        self.assertAlmostEqual(data["current_probability"]["Yes"], 0.65)

    def test_normalize_json_string_outcomes(self):
        from integrations.polymarket.client import normalize_polymarket_record

        raw = {
            "id": "999",
            "question": "Fed cut in June?",
            "outcomes": '["Yes", "No"]',
            "outcomePrices": '["0.03", "0.97"]',
            "closed": False,
        }
        data = normalize_polymarket_record(raw, default_category="Economy")
        self.assertEqual(data["category"], "Economy")
        self.assertAlmostEqual(data["current_probability"]["Yes"], 0.03)
        self.assertAlmostEqual(data["current_probability"]["No"], 0.97)

    def test_is_binary_market_record(self):
        from integrations.polymarket.client import is_binary_market_record

        self.assertTrue(
            is_binary_market_record({"outcomes": '["Yes", "No"]'})
        )
        self.assertFalse(
            is_binary_market_record({"outcomes": '["A", "B", "C"]'})
        )

    def test_build_polymarket_display_sections(self):
        from integrations.polymarket.display import build_polymarket_display_sections

        raw = {
            "id": "1",
            "question": "Test?",
            "outcomes": '["Yes", "No"]',
            "outcomePrices": '["0.5", "0.5"]',
            "volume24hr": 1000,
            "active": True,
        }
        sections = build_polymarket_display_sections(market_raw=raw)
        self.assertGreater(len(sections), 0)
        total_fields = sum(
            len(f) for s in sections for g in s["groups"] for f in [g["fields"]]
        )
        self.assertGreater(total_fields, 0)


class CommentVotingTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username="author", password="pass")
        self.voter = User.objects.create_user(username="voter", password="pass")
        self.market = Market.objects.create(
            external_id="m3",
            title="Vote test",
            slug="vote-test",
            outcomes=[{"label": "A"}],
        )
        self.comment = create_comment(user=self.author, market=self.market, body="Vote me")

    def test_upvote_increases_score(self):
        cast_vote(
            user=self.voter,
            target_type=Vote.TargetType.COMMENT,
            target_id=self.comment.id,
            value=1,
        )
        self.comment.refresh_from_db()
        self.assertGreaterEqual(self.comment.popularity_score, 1)

    def test_cannot_vote_own_content(self):
        with self.assertRaises(ValueError):
            cast_vote(
                user=self.author,
                target_type=Vote.TargetType.COMMENT,
                target_id=self.comment.id,
                value=1,
            )
