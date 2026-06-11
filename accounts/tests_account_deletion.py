"""Tests for permanent account deletion."""

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from accounts.account_deletion_services import (
    AccountDeletionError,
    delete_user_account,
    deletion_requires_email_code,
    send_deletion_confirmation_code,
    verify_deletion_confirmation_code,
)
from accounts.models import UserProfile
from comments.models import Comment, Vote
from comments.services import cast_vote, create_comment
from conftest import create_market, create_user
from predictions.models import Prediction
from predictions.services import create_prediction

User = get_user_model()


class AccountDeletionServiceTests(TestCase):
    def setUp(self):
        self.user = create_user("deleter")
        self.other = create_user("other")
        self.market = create_market(slug="delete-test-market", external_id="delete-test-market")

    def test_delete_user_removes_user_and_profile(self):
        user_id = self.user.pk
        delete_user_account(user=self.user)
        self.assertFalse(User.objects.filter(pk=user_id).exists())
        self.assertFalse(UserProfile.objects.filter(user_id=user_id).exists())

    def test_delete_user_removes_predictions_and_comments(self):
        create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
            predicted_direction=Prediction.Direction.YES,
        )
        create_comment(user=self.user, market=self.market, body="Hello")
        delete_user_account(user=self.user)
        self.assertFalse(Prediction.objects.filter(user_id=self.user.pk).exists())
        self.assertFalse(Comment.objects.filter(user_id=self.user.pk).exists())

    def test_delete_user_cleans_votes_on_their_content(self):
        prediction = create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
            predicted_direction=Prediction.Direction.YES,
        )
        comment = create_comment(user=self.user, market=self.market, body="Thread")
        cast_vote(
            user=self.other,
            target_type=Vote.TargetType.PREDICTION,
            target_id=prediction.id,
            value=1,
        )
        cast_vote(
            user=self.other,
            target_type=Vote.TargetType.COMMENT,
            target_id=comment.id,
            value=1,
        )
        delete_user_account(user=self.user)
        self.assertFalse(
            Vote.objects.filter(
                target_type=Vote.TargetType.PREDICTION,
                target_id=prediction.id,
            ).exists()
        )
        self.assertFalse(
            Vote.objects.filter(
                target_type=Vote.TargetType.COMMENT,
                target_id=comment.id,
            ).exists()
        )

    def test_superuser_cannot_be_deleted(self):
        admin = create_user("admin", is_superuser=True, is_staff=True)
        with self.assertRaises(AccountDeletionError):
            delete_user_account(user=admin)


class AccountDeletionViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = create_user("view-deleter", password="secret123")

    def test_requires_login(self):
        response = self.client.get(reverse("accounts:account_delete"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_get_shows_confirmation_page(self):
        self.client.login(username="view-deleter", password="secret123")
        response = self.client.get(reverse("accounts:account_delete"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Delete account")

    def test_post_deletes_account_and_logs_out(self):
        self.client.login(username="view-deleter", password="secret123")
        response = self.client.post(
            reverse("accounts:account_delete"),
            {
                "username_confirm": "view-deleter",
                "password": "secret123",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("dashboard:landing"))
        self.assertFalse(User.objects.filter(username="view-deleter").exists())

    def test_post_rejects_wrong_password(self):
        self.client.login(username="view-deleter", password="secret123")
        response = self.client.post(
            reverse("accounts:account_delete"),
            {
                "username_confirm": "view-deleter",
                "password": "wrong-password",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(username="view-deleter").exists())

    def test_post_rejects_wrong_username(self):
        self.client.login(username="view-deleter", password="secret123")
        response = self.client.post(
            reverse("accounts:account_delete"),
            {
                "username_confirm": "someone-else",
                "password": "secret123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(username="view-deleter").exists())

    def test_spanish_confirmation_page(self):
        self.client.login(username="view-deleter", password="secret123")
        response = self.client.get(reverse("accounts:account_delete"), HTTP_ACCEPT_LANGUAGE="es")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Eliminar cuenta")

    def test_profile_edit_links_to_delete_page(self):
        self.client.login(username="view-deleter", password="secret123")
        response = self.client.get(reverse("accounts:profile_edit"))
        self.assertContains(response, reverse("accounts:account_delete"))


class OAuthAccountDeletionReauthTests(TestCase):
    """Password-less (OAuth) accounts must confirm deletion with an emailed code."""

    def setUp(self):
        cache.clear()
        self.user = create_user("oauth-deleter")
        self.user.set_unusable_password()
        self.user.email = "oauth-deleter@test.com"
        self.user.save(update_fields=["password", "email"])
        self.client = Client()
        self.client.force_login(self.user)

    def test_oauth_account_requires_email_code(self):
        self.assertTrue(deletion_requires_email_code(self.user))

    def test_password_account_does_not_require_code(self):
        pw_user = create_user("pw-user", password="secret123")
        self.assertFalse(deletion_requires_email_code(pw_user))

    def test_send_code_emails_and_verifies(self):
        sent, _msg = send_deletion_confirmation_code(self.user)
        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        # Extract the 6-digit code from the email body.
        import re

        code = re.search(r"\b(\d{6})\b", body).group(1)
        self.assertTrue(verify_deletion_confirmation_code(self.user, code))
        # Single-use: second verification fails.
        self.assertFalse(verify_deletion_confirmation_code(self.user, code))

    def test_wrong_code_fails(self):
        send_deletion_confirmation_code(self.user)
        self.assertFalse(verify_deletion_confirmation_code(self.user, "000000"))

    def test_delete_without_code_is_rejected(self):
        response = self.client.post(
            reverse("accounts:account_delete"),
            {"username_confirm": "oauth-deleter"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(username="oauth-deleter").exists())

    def test_delete_with_valid_code_succeeds(self):
        import re

        send_deletion_confirmation_code(self.user)
        code = re.search(r"\b(\d{6})\b", mail.outbox[0].body).group(1)
        response = self.client.post(
            reverse("accounts:account_delete"),
            {"username_confirm": "oauth-deleter", "confirmation_code": code},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(username="oauth-deleter").exists())

    def test_send_code_action_from_view(self):
        response = self.client.post(
            reverse("accounts:account_delete"),
            {"action": "send_code"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
