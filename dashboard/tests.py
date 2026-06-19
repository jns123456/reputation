from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import Bookmark, User
from accounts.bookmark_services import toggle_bookmark
from conftest import create_user
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
    def setUp(self):
        cache.clear()

    def test_landing_renders_english_copy_by_default(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Domains and topics:")
        self.assertContains(response, "What we track")
        self.assertContains(response, "Compete without betting")
        self.assertContains(response, "Reputation vs Popularity")
        self.assertContains(response, "/assets/landing-hero.mp4")
        self.assertContains(response, "landing-video-poster.png")
        self.assertContains(response, "pr-landing-video__play")

    def test_landing_renders_market_tape_when_images_exist(self):
        Market.objects.create(
            external_id="landing-tape-1",
            title="Bitcoin hits 150k",
            slug="landing-tape-bitcoin",
            status=Market.Status.OPEN,
            accepting_orders=True,
            close_date=timezone.now() + timedelta(days=30),
            card_image_url="https://example.com/bitcoin.png",
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.4, "No": 0.6},
        )

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pr-market-tape")
        self.assertContains(response, "Bitcoin hits 150k")
        self.assertContains(response, "https://example.com/bitcoin.png")
        self.assertContains(response, "/markets/landing-tape-bitcoin/")

    def test_landing_renders_spanish_copy_with_language_cookie(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "es"
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dominios y temas:")
        self.assertContains(response, "Qué registramos")
        self.assertContains(response, "Compite sin apostar")
        self.assertContains(response, "Reputación vs. Popularidad")
        self.assertNotContains(response, "Domains and topics:")

    def test_landing_renders_spanish_tape_label_with_language_cookie(self):
        Market.objects.create(
            external_id="landing-tape-es",
            title="Elecciones 2028",
            slug="landing-tape-elecciones",
            status=Market.Status.OPEN,
            accepting_orders=True,
            close_date=timezone.now() + timedelta(days=30),
            card_image_url="https://example.com/election.png",
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "es"
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pronósticos abiertos destacados")
        self.assertNotContains(response, "Featured open forecasts")


class ForecastsPageTests(TestCase):
    def setUp(self):
        self.user = create_user("forecastsuser", password="pass")
        self.other = create_user("other", password="pass")
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
        self.assertContains(response, f"prediction-discussion-{self.prediction.id}")
        self.assertContains(response, "Log in")

    def test_forecasts_page_shows_comment_composer_for_other_users(self):
        self.client.login(username="forecastsuser", password="pass")
        response = self.client.get("/forecasts/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Join the conversation")

    def test_forecasts_page_hides_handle_for_anonymous_users(self):
        anon = User.objects.create_user(
            username="secretanon",
            email="anon@example.com",
            password="pass",
            identity_mode=User.IdentityMode.ANONYMOUS,
            display_name="TheBagHodler",
            onboarding_completed=True,
        )
        create_prediction(
            user=anon,
            market=self.market,
            predicted_outcome="Yes",
            reasoning="Anonymous forecast line",
        )
        response = self.client.get("/forecasts/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TheBagHodler")
        self.assertContains(response, "Anonymous forecast line")
        self.assertNotContains(response, "@secretanon")

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
        self.assertContains(response, "pr-vote-thumb-icon")
        self.assertContains(response, "hx-swap-oob")

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
