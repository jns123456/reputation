from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from accounts.user_search_selectors import (
    count_browsable_users,
    get_browsable_users,
    normalize_user_search_query,
    search_user_matches,
    search_users,
)


class UserSearchSelectorTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice",
            password="pass",
            email="alice@predictstamp.app",
            display_name="Alice Predictor",
            bio="Crypto and politics forecasts.",
        )
        User.objects.create_user(
            username="bob",
            password="pass",
            email="bob.sports@example.com",
            bio="Sports only.",
        )
        User.objects.create_user(
            username="ghost",
            password="pass",
            identity_mode=User.IdentityMode.ANONYMOUS,
            display_name="Hidden Ghost",
        )

    def test_search_requires_minimum_length(self):
        self.assertEqual(search_users(query="a"), [])

    def test_search_matches_username(self):
        results = search_users(query="bob")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].username, "bob")

    def test_search_matches_username_with_at_prefix(self):
        results = search_users(query="@alice")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].username, "alice")

    def test_search_matches_display_name(self):
        results = search_users(query="Alice")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].username, "alice")

    def test_search_does_not_match_full_email(self):
        # Looking up a full address must not confirm the account exists.
        for user in search_users(query="bob.sports@example.com"):
            self.assertNotEqual(user.username, "bob")

    def test_search_never_matches_email(self):
        # Email matching would let anyone confirm which addresses have
        # accounts (enumeration) — it must never surface results.
        self.assertEqual(search_users(query="bob.sports"), [])

    def test_search_matches_bio(self):
        results = search_users(query="Sports")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].username, "bob")

    def test_anonymous_users_are_excluded(self):
        self.assertEqual(search_users(query="ghost"), [])
        self.assertEqual(search_users(query="Hidden"), [])

    def test_fuzzy_match_finds_close_username(self):
        results = search_user_matches(query="alic")
        usernames = {user.username for user in results.users}
        self.assertIn("alice", usernames)

    def test_similar_results_are_grouped(self):
        results = search_user_matches(query="alic")
        self.assertTrue(results.exact_users or results.similar_users)

    def test_normalize_strips_leading_at(self):
        self.assertEqual(normalize_user_search_query("@alice"), "alice")

    def test_browsable_users_exclude_anonymous(self):
        self.assertEqual(count_browsable_users(), 2)
        usernames = {user.username for user in get_browsable_users()}
        self.assertEqual(usernames, {"alice", "bob"})

    def test_hidden_users_are_excluded_from_search_and_directory(self):
        User.objects.create_user(
            username="privateuser",
            password="pass",
            email="private@example.com",
            display_name="Private User",
            hide_from_user_directory=True,
        )
        self.assertEqual(search_users(query="private"), [])
        self.assertEqual(search_users(query="Private"), [])
        usernames = {user.username for user in get_browsable_users()}
        self.assertNotIn("privateuser", usernames)


class UserSearchViewTests(TestCase):
    def setUp(self):
        User.objects.create_user(
            username="searchable",
            password="pass",
            email="searchable@example.com",
            display_name="Searchable User",
            onboarding_completed=True,
            email_verified_at=timezone.now(),
        )
        self.client = Client()

    def test_user_search_redirects_to_user_list(self):
        response = self.client.get("/accounts/users/search/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/accounts/users/list/")

    def test_user_search_redirects_with_query(self):
        response = self.client.get("/accounts/users/search/?q=Searchable")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/accounts/users/list/?q=Searchable")

    def test_user_list_page_finds_user(self):
        response = self.client.get("/accounts/users/list/?q=Searchable")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Searchable User")

    def test_user_list_page_shows_follow_button(self):
        from conftest import create_user

        self.client.force_login(User.objects.get(username="searchable"))
        other = create_user("otheruser", display_name="Other User")
        response = self.client.get("/accounts/users/list/?q=Other")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Follow")
        self.assertContains(response, f"follow-user-{other.username}")

    def test_user_list_page_shows_unfollow_for_followed_user(self):
        from accounts.follow_services import toggle_follow
        from conftest import create_user

        viewer = create_user("viewer")
        target = User.objects.get(username="searchable")
        toggle_follow(follower=viewer, following_user=target)
        self.client.force_login(viewer)
        response = self.client.get("/accounts/users/list/?q=Searchable")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unfollow")

    def test_user_list_page_finds_user_by_email(self):
        response = self.client.get("/accounts/users/list/?q=searchable@example.com")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Searchable User")

    def test_user_list_page_has_search_form(self):
        response = self.client.get("/accounts/users/list/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="user-list-search-q"')
        self.assertContains(response, "Search")

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

    def test_user_list_page_renders_browsable_users(self):
        response = self.client.get("/accounts/users/list/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "All users")
        self.assertContains(response, "Searchable User")
        self.assertNotContains(response, "Search users →")

    def test_forum_sidebar_links_to_user_list(self):
        response = self.client.get("/forum/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("accounts:user_list"))

    def test_anonymous_users_excluded_from_browsable_list(self):
        User.objects.create_user(
            username="ghostlist",
            password="pass",
            identity_mode=User.IdentityMode.ANONYMOUS,
            display_name="Ghost List",
        )
        response = self.client.get("/accounts/users/list/")
        self.assertNotContains(response, "Ghost List")

    def test_hidden_user_excluded_from_browsable_list(self):
        User.objects.create_user(
            username="hiddenlist",
            password="pass",
            display_name="Hidden List User",
            hide_from_user_directory=True,
        )
        response = self.client.get("/accounts/users/list/")
        self.assertNotContains(response, "Hidden List User")

    def test_profile_edit_can_hide_from_user_directory(self):
        from conftest import create_user

        user = create_user("edithidden", display_name="Edit Hidden")
        self.client.force_login(user)
        response = self.client.post(
            reverse("accounts:profile_edit"),
            {
                "email": user.email,
                "bio": "",
                "display_name": "Edit Hidden",
                "identity_mode": User.IdentityMode.PUBLIC,
                "hide_from_user_directory": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertTrue(user.hide_from_user_directory)
        self.client.logout()
        list_response = self.client.get("/accounts/users/list/?q=Edit")
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "No users match")
        self.assertNotContains(list_response, f"follow-user-{user.username}")