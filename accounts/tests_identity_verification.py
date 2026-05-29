"""Tests for platform identity verification review."""

from django.test import TestCase

from accounts.identity_verification_services import (
    IdentityVerificationError,
    approve_identity_verification,
    get_pending_verification_users,
    reject_identity_verification,
)
from accounts.models import User
from conftest import create_user


class IdentityVerificationServiceTests(TestCase):
    def setUp(self):
        self.pending = create_user(
            username="pending",
            verification_requested=True,
            is_verified=False,
        )

    def test_get_pending_verification_users(self):
        create_user(username="verified", verification_requested=True, is_verified=True)
        create_user(username="none", verification_requested=False, is_verified=False)

        pending = list(get_pending_verification_users())
        self.assertEqual(pending, [self.pending])

    def test_approve_identity_verification(self):
        approve_identity_verification(self.pending)
        self.pending.refresh_from_db()
        self.assertTrue(self.pending.is_verified)
        self.assertTrue(self.pending.verification_requested)

    def test_reject_identity_verification(self):
        reject_identity_verification(self.pending)
        self.pending.refresh_from_db()
        self.assertFalse(self.pending.verification_requested)
        self.assertFalse(self.pending.is_verified)

    def test_approve_raises_when_not_pending(self):
        user = create_user(username="plain")
        with self.assertRaises(IdentityVerificationError):
            approve_identity_verification(user)


class AdminPanelVerificationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="superadmin",
            email="admin@example.com",
            password="testpass123",
            onboarding_completed=True,
            email_verified_at=self._now(),
        )
        self.pending = create_user(
            username="reviewme",
            display_name="Review Me",
            verification_requested=True,
            is_verified=False,
        )
        self.client.login(username="superadmin", password="testpass123")

    @staticmethod
    def _now():
        from django.utils import timezone

        return timezone.now()

    def test_admin_panel_lists_pending_verification(self):
        response = self.client.get("/panel/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Review Me")
        self.assertContains(response, "Approve")
        self.assertContains(response, "Reject")

    def test_approve_from_admin_panel(self):
        response = self.client.post(
            f"/panel/verifications/{self.pending.pk}/",
            {"action": "approve"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.pending.refresh_from_db()
        self.assertTrue(self.pending.is_verified)
        self.assertNotContains(response, "Review Me")

    def test_reject_from_admin_panel(self):
        response = self.client.post(
            f"/panel/verifications/{self.pending.pk}/",
            {"action": "reject"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.pending.refresh_from_db()
        self.assertFalse(self.pending.verification_requested)

    def test_non_superuser_cannot_resolve(self):
        user = create_user(username="regular")
        self.client.login(username="regular", password="testpass123")
        response = self.client.post(
            f"/panel/verifications/{self.pending.pk}/",
            {"action": "approve"},
        )
        self.assertEqual(response.status_code, 302)
        self.pending.refresh_from_db()
        self.assertFalse(self.pending.is_verified)
