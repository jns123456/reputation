from django.test import Client, TestCase
from django.urls import reverse

from conftest import create_user


class ProfileMonetizeViewTests(TestCase):
    def setUp(self):
        self.owner = create_user("creator")
        self.visitor = create_user("visitor")
        self.client = Client()

    def test_monetize_page_renders_for_owner(self):
        self.client.force_login(self.owner)
        url = reverse(
            "accounts:profile_monetize",
            kwargs={"username": self.owner.username},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Make money doing the")
        self.assertContains(response, "Set up creator program")
        self.assertContains(response, "Estimate your earnings")

    def test_monetize_page_renders_for_anonymous_visitor(self):
        url = reverse(
            "accounts:profile_monetize",
            kwargs={"username": self.owner.username},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Your creator hub")
        self.assertContains(response, "View profile")

    def test_profile_header_links_monetize_for_owner_only(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("accounts:profile", kwargs={"username": self.owner.username})
        )
        self.assertContains(
            response,
            reverse(
                "accounts:profile_monetize",
                kwargs={"username": self.owner.username},
            ),
        )
        self.assertContains(response, "Monetize")

    def test_profile_header_hides_monetize_for_other_users(self):
        self.client.force_login(self.visitor)
        response = self.client.get(
            reverse("accounts:profile", kwargs={"username": self.owner.username})
        )
        self.assertNotContains(
            response,
            reverse(
                "accounts:profile_monetize",
                kwargs={"username": self.owner.username},
            ),
        )

    def test_spanish_monetize_page(self):
        url = reverse(
            "accounts:profile_monetize",
            kwargs={"username": self.owner.username},
        )
        response = self.client.get(url, HTTP_ACCEPT_LANGUAGE="es")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Monetiza tu contenido")
        self.assertContains(response, "Gana dinero haciendo el")
