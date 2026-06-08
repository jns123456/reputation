"""Tests for permanent account deletion."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.account_deletion_services import AccountDeletionError, delete_user_account
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
