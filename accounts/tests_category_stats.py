from django.test import TestCase

from accounts.category_selectors import get_user_category_breakdown
from accounts.models import User, UserCategoryStats
from comments.models import Vote
from comments.services import cast_vote, create_comment
from markets.models import Market
from predictions.services import create_prediction, exit_prediction, resolve_market_predictions


class CategoryStatsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="expert", password="pass")
        self.voter = User.objects.create_user(username="fan", password="pass")
        self.market = Market.objects.create(
            external_id="crypto-1",
            title="BTC above 100k?",
            slug="btc-100k",
            category="Crypto",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.2, "No": 0.8},
            polymarket_raw={"tags": [{"slug": "crypto"}]},
        )

    def test_prediction_and_reputation_update_category_stats(self):
        prediction = create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
        )
        stats = UserCategoryStats.objects.get(user=self.user, category_slug="crypto")
        self.assertEqual(stats.prediction_count, 1)

        self.market.status = Market.Status.RESOLVED
        self.market.resolved_outcome = "Yes"
        self.market.save()
        resolve_market_predictions(self.market)

        stats.refresh_from_db()
        self.assertEqual(stats.reputation_points, 80)
        self.assertEqual(stats.scored_forecast_count, 1)
        self.assertEqual(stats.reputation_score, 26.67)
        self.assertEqual(stats.correct_prediction_count, 1)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.reputation_points, 80)

        breakdown = get_user_category_breakdown(self.user)
        crypto_row = next(row for row in breakdown if row["category"].slug == "crypto")
        politics_row = next(row for row in breakdown if row["category"].slug == "politics")
        self.assertEqual(crypto_row["reputation_points"], 80)
        self.assertEqual(politics_row["reputation_points"], 0)

    def test_vote_updates_category_popularity(self):
        comment = create_comment(user=self.user, market=self.market, body="BTC moon")
        cast_vote(
            user=self.voter,
            target_type=Vote.TargetType.COMMENT,
            target_id=comment.id,
            value=1,
        )
        stats = UserCategoryStats.objects.get(user=self.user, category_slug="crypto")
        self.assertEqual(stats.popularity_points, 1)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.popularity_points, 1)

    def test_category_scores_sum_to_global_on_single_category_activity(self):
        create_prediction(user=self.user, market=self.market, predicted_outcome="Yes")
        comment = create_comment(user=self.user, market=self.market, body="Discuss")
        cast_vote(
            user=self.voter,
            target_type=Vote.TargetType.COMMENT,
            target_id=comment.id,
            value=1,
        )

        self.market.status = Market.Status.RESOLVED
        self.market.resolved_outcome = "Yes"
        self.market.save()
        resolve_market_predictions(self.market)

        breakdown = get_user_category_breakdown(self.user)
        total_rep = sum(row["reputation_points"] for row in breakdown)
        total_pop = sum(row["popularity_points"] for row in breakdown)
        self.user.profile.refresh_from_db()
        self.assertEqual(total_rep, self.user.profile.reputation_points)
        self.assertEqual(total_pop, self.user.profile.popularity_points)

    def test_exit_updates_category_correct_counts(self):
        prediction = create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
        )
        self.market.current_probability = {"Yes": 0.55, "No": 0.45}
        self.market.save(update_fields=["current_probability"])
        exit_prediction(prediction=prediction, user=self.user)

        stats = UserCategoryStats.objects.get(user=self.user, category_slug="crypto")
        self.assertEqual(stats.scored_forecast_count, 1)
        self.assertEqual(stats.correct_prediction_count, 1)
        self.assertEqual(stats.incorrect_prediction_count, 0)
        self.assertEqual(stats.reputation_points, 35)
