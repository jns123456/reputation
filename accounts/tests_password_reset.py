"""Tests for the password reset flow (request → email → confirm → complete)."""

import json
import re
from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from conftest import create_user


class PasswordResetFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = create_user("resetter", password="OldPass123!")
        self.user.email = "resetter@test.com"
        self.user.save(update_fields=["email"])
        self.client = Client()

    def test_form_page_renders(self):
        response = self.client.get(reverse("accounts:password_reset"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reset your password")

    def test_form_page_renders_in_spanish(self):
        response = self.client.get(
            reverse("accounts:password_reset"), HTTP_ACCEPT_LANGUAGE="es"
        )
        self.assertEqual(response.status_code, 200)

    def test_login_page_links_to_reset(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertContains(response, reverse("accounts:password_reset"))

    def test_request_sends_email_with_working_link(self):
        response = self.client.post(
            reverse("accounts:password_reset"), {"email": "resetter@test.com"}
        )
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)

        match = re.search(r"(/accounts/password-reset/[^/\s]+/[^/\s]+/)", mail.outbox[0].body)
        self.assertIsNotNone(match)
        reset_path = match.group(1)

        # Django redirects the tokenized URL to a session-backed set-password URL.
        response = self.client.get(reset_path, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "New password")

        # Complete the reset on the redirected URL.
        set_password_url = response.request["PATH_INFO"]
        response = self.client.post(
            set_password_url,
            {"new_password1": "BrandNewPass456!", "new_password2": "BrandNewPass456!"},
        )
        self.assertRedirects(response, reverse("accounts:password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("BrandNewPass456!"))

    def test_unknown_email_does_not_reveal_accounts(self):
        # Same redirect + no error whether or not the account exists.
        response = self.client.post(
            reverse("accounts:password_reset"), {"email": "ghost@test.com"}
        )
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_invalid_token_shows_error_state(self):
        response = self.client.get("/accounts/password-reset/abc/def-token/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "invalid")

    @override_settings(RESEND_API_KEY="re_test_key")
    @patch("requests.post")
    def test_request_via_resend_serializes_translated_subject(self, mock_post):
        mock_post.return_value.status_code = 200

        response = self.client.post(
            reverse("accounts:password_reset"),
            {"email": "resetter@test.com"},
            HTTP_ACCEPT_LANGUAGE="es",
        )

        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        mock_post.assert_called_once()
        payload = mock_post.call_args.kwargs["json"]
        json.dumps(payload)
        self.assertIsInstance(payload["subject"], str)
        self.assertIn("contraseña", payload["subject"].lower())

    @override_settings(ABUSE_RATE_LIMITS={"password_reset": {"ip": (1, 3600)}})
    def test_request_is_rate_limited_by_ip(self):
        first = self.client.post(
            reverse("accounts:password_reset"), {"email": "resetter@test.com"}
        )
        self.assertEqual(first.status_code, 302)
        second = self.client.post(
            reverse("accounts:password_reset"), {"email": "resetter@test.com"}
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
