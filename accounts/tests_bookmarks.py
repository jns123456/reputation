from django.test import Client, TestCase

from accounts.models import Bookmark, User
from accounts.bookmark_services import toggle_bookmark
from markets.models import Market
from predictions.services import create_prediction


class BookmarksPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="saver", password="pass")
        self.author = User.objects.create_user(username="author", password="pass")
        self.market = Market.objects.create(
            external_id="bookmark-m1",
            title="Bookmark market",
            slug="bookmark-market",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )
        self.prediction = create_prediction(
            user=self.author,
            market=self.market,
            predicted_outcome="Yes",
            reasoning="Worth saving.",
        )
        self.client = Client()

    def test_bookmarks_page_requires_login(self):
        response = self.client.get("/accounts/bookmarks/")
        self.assertEqual(response.status_code, 302)

    def test_bookmarks_page_lists_saved_forecast(self):
        toggle_bookmark(
            user=self.user,
            target_type=Bookmark.TargetType.PREDICTION,
            target_id=self.prediction.id,
        )
        self.client.login(username="saver", password="pass")
        response = self.client.get("/accounts/bookmarks/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Worth saving.")
        self.assertContains(response, "Bookmark market")

    def test_bookmarks_filter_by_type(self):
        toggle_bookmark(
            user=self.user,
            target_type=Bookmark.TargetType.PREDICTION,
            target_id=self.prediction.id,
        )
        self.client.login(username="saver", password="pass")
        response = self.client.get("/accounts/bookmarks/?type=prediction")
        self.assertContains(response, "Worth saving.")
        response = self.client.get("/accounts/bookmarks/?type=pulse_post")
        self.assertNotContains(response, "Worth saving.")
