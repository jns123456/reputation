"""Tests for signup email verification flow."""

from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.email_verification_services import (
    create_verification_token,
    resend_verification_email,
    send_verification_email,
    verify_email_with_token,
)
from accounts.models import EmailVerificationToken, User
from conftest import create_user


@override_settings(
    EMAIL_VERIFICATION_REQUIRED=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SITE_BASE_URL="http://testserver",
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    },
)
class EmailVerificationServiceTests(TestCase):
    def setUp(self):
        self.user = create_user(
            "newbie",
            email="newbie@example.com",
            email_verified_at=None,
        )

    def test_send_verification_email_creates_token_and_message(self):
        mail.outbox = []
        self.assertTrue(send_verification_email(self.user))

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["newbie@example.com"])
        self.assertIn("/accounts/verify-email/", mail.outbox[0].body)
        self.assertEqual(EmailVerificationToken.objects.filter(user=self.user).count(), 1)

    def test_verify_token_marks_user_verified(self):
        token = create_verification_token(self.user)
        result = verify_email_with_token(token.token)

        self.assertTrue(result.success)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.email_verified_at)
        token.refresh_from_db()
        self.assertIsNotNone(token.used_at)

    def test_expired_token_is_rejected(self):
        token = create_verification_token(self.user)
        EmailVerificationToken.objects.filter(pk=token.pk).update(
            expires_at=timezone.now() - timezone.timedelta(minutes=1)
        )
        result = verify_email_with_token(token.token)
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "expired")

    def test_token_invalid_after_email_change(self):
        token = create_verification_token(self.user)
        self.user.email = "changed@example.com"
        self.user.save(update_fields=["email"])
        result = verify_email_with_token(token.token)
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "email_changed")

    def test_resend_has_cooldown(self):
        mail.outbox = []
        ok, _message = resend_verification_email(self.user)
        self.assertTrue(ok)
        self.assertEqual(len(mail.outbox), 1)

        ok, message = resend_verification_email(self.user)
        self.assertFalse(ok)
        self.assertEqual(len(mail.outbox), 1)


@override_settings(
    EMAIL_VERIFICATION_REQUIRED=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    },
)
class EmailVerificationViewTests(TestCase):
    def test_signup_redirects_to_pending_and_sends_email(self):
        mail.outbox = []
        client = Client()
        response = client.post(
            reverse("accounts:signup"),
            {
                "username": "freshuser",
                "email": "fresh@example.com",
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
            },
        )

        self.assertRedirects(response, reverse("accounts:verify_email_pending"))
        user = User.objects.get(username="freshuser")
        self.assertIsNone(user.email_verified_at)
        self.assertEqual(len(mail.outbox), 1)

    def test_unverified_user_is_redirected_from_markets(self):
        user = create_user("locked", email_verified_at=None)
        client = Client()
        client.force_login(user)

        response = client.get("/markets/", follow=False)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("accounts:verify_email_pending"))

    def test_verify_link_logs_in_and_continues_setup(self):
        user = create_user("verifyme", email_verified_at=None)
        token = create_verification_token(user)
        client = Client()

        response = client.get(reverse("accounts:verify_email_confirm", args=[token.token]))

        self.assertRedirects(response, reverse("accounts:profile_setup"))
        user.refresh_from_db()
        self.assertIsNotNone(user.email_verified_at)

        response = client.get(reverse("accounts:profile_setup"))
        self.assertEqual(response.status_code, 200)
