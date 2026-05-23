from django.test import Client, TestCase

from accounts.models import Bookmark, User
from accounts.bookmark_services import toggle_bookmark
from markets.models import Market
from predictions.models import Prediction
from predictions.services import create_prediction


class ForumPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="forumuser", password="pass")
        self.other = User.objects.create_user(username="other", password="pass")
        self.market = Market.objects.create(
            external_id="forum-m1",
            title="Forum test market",
            slug="forum-test-market",
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

    def test_forum_page_lists_forecasts(self):
        response = self.client.get("/forum/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Forum")
        self.assertContains(response, "Strong signal from on-chain data.")
        self.assertContains(response, "Forum test market")

    def test_forum_feed_filters_by_market(self):
        other_market = Market.objects.create(
            external_id="forum-m2",
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

        response = self.client.get("/forum/feed/?market=forum-test-market")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Strong signal")
        self.assertNotContains(response, "Different market forecast")

    def test_forum_vote_toggle_via_htmx(self):
        self.client.login(username="forumuser", password="pass")
        response = self.client.post(
            "/comments/vote/",
            {
                "target_type": "prediction",
                "target_id": self.prediction.id,
                "value": "1",
                "layout": "forum",
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
                "layout": "forum",
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "is-active")

    def test_bookmark_toggle(self):
        self.client.login(username="forumuser", password="pass")
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
