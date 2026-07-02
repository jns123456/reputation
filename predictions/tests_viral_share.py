"""Tests for public challenge cards and @ profile URLs."""

from django.test import TestCase
from django.urls import reverse

from challenges.models import Challenge, ChallengeParticipant
from conftest import create_user


class ChallengeCardTests(TestCase):
    def setUp(self):
        self.creator = create_user("challenger")
        self.opponent = create_user("challenged")
        self.challenge = Challenge.objects.create(
            creator=self.creator,
            title="World Cup duel",
            status=Challenge.Status.ACTIVE,
        )
        ChallengeParticipant.objects.create(
            challenge=self.challenge,
            user=self.creator,
            status=ChallengeParticipant.Status.ACCEPTED,
        )
        ChallengeParticipant.objects.create(
            challenge=self.challenge,
            user=self.opponent,
            status=ChallengeParticipant.Status.ACCEPTED,
            invite_token="test-invite-token",
        )

    def test_public_challenge_card_renders(self):
        response = self.client.get(reverse("challenge_card", args=[self.challenge.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "World Cup duel")
        self.assertContains(response, "PredictStamp Challenge")

    def test_challenge_og_image_returns_png(self):
        response = self.client.get(reverse("challenge_card_og", args=[self.challenge.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")


class ProfileAtUrlTests(TestCase):
    def setUp(self):
        self.user = create_user("viralprofile")

    def test_at_username_redirects_to_profile(self):
        response = self.client.get(f"/@{self.user.username}/")
        self.assertRedirects(
            response,
            reverse("accounts:profile", args=[self.user.username]),
            fetch_redirect_response=False,
        )

    def test_profile_og_image_returns_png(self):
        response = self.client.get(
            reverse("accounts:profile_og", args=[self.user.username])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")

    def test_profile_page_has_share_button(self):
        response = self.client.get(
            reverse("accounts:profile", args=[self.user.username])
        )
        self.assertContains(response, "Share profile")
