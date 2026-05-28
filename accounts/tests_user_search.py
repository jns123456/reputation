from django.test import Client, TestCase

from accounts.models import User
from accounts.selectors import search_users


class UserSearchSelectorTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice",
            password="pass",
            display_name="Alice Predictor",
            bio="Crypto and politics forecasts.",
        )
        User.objects.create_user(username="bob", password="pass", bio="Sports only.")

    def test_search_requires_minimum_length(self):
        self.assertEqual(search_users(query="a").count(), 0)

    def test_search_matches_username(self):
        results = list(search_users(query="bob"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].username, "bob")

    def test_search_matches_display_name(self):
        results = list(search_users(query="Alice"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].username, "alice")

    def test_search_matches_bio(self):
        results = list(search_users(query="Sports"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].username, "bob")


class UserSearchViewTests(TestCase):
    def setUp(self):
        User.objects.create_user(
            username="searchable",
            password="pass",
            display_name="Searchable User",
            onboarding_completed=True,
        )
        self.client = Client()

    def test_user_search_page_renders(self):
        response = self.client.get("/accounts/users/search/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Find users")

    def test_user_search_page_finds_user(self):
        response = self.client.get("/accounts/users/search/?q=Searchable")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Searchable User")

    def test_user_search_partial_returns_matches(self):
        response = self.client.get("/accounts/users/search/partial/?q=search")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Searchable User")

    def test_user_search_partial_empty_for_short_query(self):
        response = self.client.get("/accounts/users/search/partial/?q=a")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Searchable User")

    def test_profile_page_links_to_user_search(self):
        self.client.login(username="searchable", password="pass")
        response = self.client.get("/accounts/users/searchable/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Find users")

    def test_forum_sidebar_includes_user_search(self):
        response = self.client.get("/forum/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Search users")
