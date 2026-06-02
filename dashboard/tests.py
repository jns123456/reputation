from django.conf import settings
from django.test import Client, TestCase

from accounts.models import Bookmark, User
from accounts.bookmark_services import toggle_bookmark
from markets.models import Market
from predictions.models import Prediction
from predictions.services import create_prediction


class StaticPageTests(TestCase):
    def test_legal_page_shows_company_details(self):
        response = self.client.get("/legal/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TAO FACTORY LLC")
        self.assertContains(response, "ops@predictstamp.com")
        self.assertContains(response, "No financial services")

    def test_terms_page_shows_operator_and_no_betting_notice(self):
        response = self.client.get("/terms/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TAO FACTORY LLC")
        self.assertContains(response, "ops@predictstamp.com")
        self.assertContains(response, "No betting or trading")


class LandingPageI18nTests(TestCase):
    def test_landing_renders_english_copy_by_default(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Domains and topics:")
        self.assertContains(response, "What we track")
        self.assertContains(response, "Compete without betting")
        self.assertContains(response, "Reputation vs Popularity")

    def test_landing_renders_spanish_copy_with_language_cookie(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "es"
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dominios y temas:")
        self.assertContains(response, "Qué registramos")
        self.assertContains(response, "Compite sin apostar")
        self.assertContains(response, "Reputación vs. Popularidad")
        self.assertNotContains(response, "Domains and topics:")


class ForecastsPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="forecastsuser", password="pass")
        self.other = User.objects.create_user(username="other", password="pass")
        self.market = Market.objects.create(
            external_id="forecasts-m1",
            title="Forecasts test market",
            slug="forecasts-test-market",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )
        self.prediction = create_prediction(
            user=self.other,
            market=self.market,
            predicted_outcome="Yes",
            reasoning="Strong signal from on-chain data.",
        )
        self.client = Client()

    def test_forecasts_page_lists_forecasts(self):
        response = self.client.get("/forecasts/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Forecasts")
        self.assertContains(response, "Strong signal from on-chain data.")
        self.assertContains(response, "Forecasts test market")

    def test_forecasts_feed_filters_by_market(self):
        other_market = Market.objects.create(
            external_id="forecasts-m2",
            title="Other market",
            slug="other-market",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )
        create_prediction(
            user=self.other,
            market=other_market,
            predicted_outcome="No",
            reasoning="Different market forecast",
        )

        response = self.client.get("/forecasts/feed/?market=forecasts-test-market")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Strong signal")
        self.assertNotContains(response, "Different market forecast")

    def test_forecasts_vote_toggle_via_htmx(self):
        self.client.login(username="forecastsuser", password="pass")
        response = self.client.post(
            "/comments/vote/",
            {
                "target_type": "prediction",
                "target_id": self.prediction.id,
                "value": "1",
                "layout": "forecasts",
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "is-active")

        response = self.client.post(
            "/comments/vote/",
            {
                "target_type": "prediction",
                "target_id": self.prediction.id,
                "value": "1",
                "layout": "forecasts",
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "is-active")

    def test_bookmark_toggle(self):
        self.client.login(username="forecastsuser", password="pass")
        self.assertFalse(
            Bookmark.objects.filter(
                user=self.user,
                target_type=Bookmark.TargetType.PREDICTION,
                target_id=self.prediction.id,
            ).exists()
        )

        response = self.client.post(
            "/accounts/bookmarks/toggle/",
            {
                "target_type": Bookmark.TargetType.PREDICTION,
                "target_id": self.prediction.id,
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Bookmark.objects.filter(
                user=self.user,
                target_type=Bookmark.TargetType.PREDICTION,
                target_id=self.prediction.id,
            ).exists()
        )

        toggle_bookmark(
            user=self.user,
            target_type=Bookmark.TargetType.PREDICTION,
            target_id=self.prediction.id,
        )
        self.assertFalse(
            Bookmark.objects.filter(
                user=self.user,
                target_type=Bookmark.TargetType.PREDICTION,
                target_id=self.prediction.id,
            ).exists()
        )


class ReputationLeaderboardI18nTests(TestCase):
    def test_reputation_leaderboard_renders_spanish_relative_mode(self):
        client = Client()
        client.cookies[settings.LANGUAGE_COOKIE_NAME] = "es"
        response = client.get("/leaderboard/reputation/?mode=relative")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ranking relativo")
        self.assertContains(response, "Rep / pronóstico")
        self.assertContains(response, "Exactitud")
        self.assertContains(response, "reputación media por pronóstico puntuado")
        self.assertContains(response, "Solo califican quienes tienen más de 10 pronósticos puntuados")
        self.assertContains(response, "data-leaderboard-sort")
        self.assertNotContains(response, "Relative ranking")

    def test_reputation_leaderboard_renders_spanish_absolute_mode(self):
        client = Client()
        client.cookies[settings.LANGUAGE_COOKIE_NAME] = "es"
        response = client.get("/leaderboard/reputation/?mode=absolute")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ranking absoluto")
        self.assertContains(response, "puntos totales de reputación")
        self.assertNotContains(response, "Absolute ranking")


class ReputationLeaderboardAccuracyFilterTests(TestCase):
    def test_resolved_forecast_accuracy_filter(self):
        from types import SimpleNamespace

        from dashboard.templatetags.reputation_filters import resolved_forecast_accuracy

        row = SimpleNamespace(correct_prediction_count=7, incorrect_prediction_count=3)
        self.assertEqual(resolved_forecast_accuracy(row), 70)
        self.assertIsNone(
            resolved_forecast_accuracy(SimpleNamespace(correct_prediction_count=0, incorrect_prediction_count=0))
        )
