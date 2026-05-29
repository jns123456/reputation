from django.test import Client, TestCase
from django.urls import reverse

from accounts.follow_services import toggle_follow
from accounts.models import UserFollow
from conftest import create_user


class ProfileConnectionsViewTests(TestCase):
    def setUp(self):
        self.viewer = create_user("viewer")
        self.star = create_user("star")
        self.fan = create_user("fan")
        toggle_follow(follower=self.fan, following_user=self.star)
        toggle_follow(follower=self.viewer, following_user=self.star)
        toggle_follow(follower=self.viewer, following_user=self.fan)
        self.client = Client()

    def test_followers_list_shows_followers(self):
        response = self.client.get(
            reverse("accounts:profile_followers", kwargs={"username": self.star.username})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.fan.public_name)
        self.assertContains(response, self.viewer.public_name)

    def test_following_list_shows_following(self):
        response = self.client.get(
            reverse("accounts:profile_following", kwargs={"username": self.viewer.username})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.star.public_name)
        self.assertContains(response, self.fan.public_name)

    def test_empty_followers_message(self):
        lonely = create_user("lonely")
        response = self.client.get(
            reverse("accounts:profile_followers", kwargs={"username": lonely.username})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No followers yet")

    def test_profile_header_links_to_connection_lists(self):
        response = self.client.get(
            reverse("accounts:profile", kwargs={"username": self.star.username})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("accounts:profile_followers", kwargs={"username": self.star.username}))
        self.assertContains(response, reverse("accounts:profile_following", kwargs={"username": self.star.username}))

    def test_followers_selector_excludes_unrelated_users(self):
        outsider = create_user("outsider")
        response = self.client.get(
            reverse("accounts:profile_followers", kwargs={"username": self.star.username})
        )
        self.assertNotContains(response, outsider.public_name)
