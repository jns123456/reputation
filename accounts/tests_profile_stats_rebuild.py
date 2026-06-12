from django.test import TestCase

from accounts.models import User
from accounts.profile_stats_services import rebuild_profile_reputation_counters
from markets.models import Market
from predictions.services import create_prediction, exit_prediction
from reputation.models import ReputationEvent


class ProfileStatsRebuildTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rebuild-user", password="pass")
        self.market = Market.objects.create(
            external_id="rebuild-m1",
            title="Rebuild market",
            slug="rebuild-market",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.4, "No": 0.6},
        )

    def test_rebuild_includes_retroactive_exit_counts(self):
        prediction = create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
        )
        self.market.current_probability = {"Yes": 0.55, "No": 0.45}
        self.market.save(update_fields=["current_probability"])
        exit_prediction(prediction=prediction, user=self.user)

        profile = self.user.profile
        profile.correct_prediction_count = 0
        profile.incorrect_prediction_count = 0
        profile.scored_forecast_count = 0
        profile.save(
            update_fields=[
                "correct_prediction_count",
                "incorrect_prediction_count",
                "scored_forecast_count",
                "updated_at",
            ]
        )

        updated = rebuild_profile_reputation_counters()
        profile.refresh_from_db()

        self.assertEqual(updated, 1)
        self.assertEqual(profile.scored_forecast_count, 1)
        self.assertEqual(profile.correct_prediction_count, 1)
        self.assertEqual(profile.incorrect_prediction_count, 0)
        self.assertEqual(
            ReputationEvent.objects.filter(
                user=self.user,
                event_type=ReputationEvent.EventType.EXITED_PREDICTION,
            ).count(),
            1,
        )
