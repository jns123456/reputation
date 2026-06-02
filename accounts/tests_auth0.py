from django.test import TestCase
from django.utils import timezone

from accounts.auth0 import get_or_create_user_from_auth0
from accounts.models import User


class GetOrCreateUserFromAuth0Tests(TestCase):
    def _userinfo(self, **overrides):
        data = {
            "sub": "auth0|abc123",
            "email": "Alice@Example.com",
            "email_verified": True,
            "nickname": "alice",
        }
        data.update(overrides)
        return data

    def test_creates_new_user_with_unusable_password(self):
        user = get_or_create_user_from_auth0(self._userinfo())

        self.assertEqual(user.auth0_sub, "auth0|abc123")
        self.assertEqual(user.email, "alice@example.com")
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.onboarding_completed)

    def test_verified_email_stamps_email_verified_at(self):
        user = get_or_create_user_from_auth0(self._userinfo(email_verified=True))
        self.assertIsNotNone(user.email_verified_at)

    def test_unverified_email_does_not_stamp_verification(self):
        user = get_or_create_user_from_auth0(self._userinfo(email_verified=False))
        self.assertIsNone(user.email_verified_at)

    def test_returns_same_user_when_sub_matches(self):
        first = get_or_create_user_from_auth0(self._userinfo())
        again = get_or_create_user_from_auth0(self._userinfo(nickname="changed"))
        self.assertEqual(first.pk, again.pk)
        self.assertEqual(User.objects.count(), 1)

    def test_links_existing_local_account_by_email_when_verified(self):
        existing = User.objects.create_user(
            username="alice_local",
            email="alice@example.com",
            password="pw-not-relevant",
        )
        existing.email_verified_at = timezone.now()
        existing.save(update_fields=["email_verified_at"])
        self.assertEqual(existing.auth0_sub, "")

        linked = get_or_create_user_from_auth0(self._userinfo())

        self.assertEqual(linked.pk, existing.pk)
        linked.refresh_from_db()
        self.assertEqual(linked.auth0_sub, "auth0|abc123")
        self.assertIsNotNone(linked.email_verified_at)
        self.assertEqual(User.objects.count(), 1)

    def test_generates_unique_username_on_collision(self):
        User.objects.create_user(username="alice", email="other@example.com")

        user = get_or_create_user_from_auth0(self._userinfo())

        self.assertNotEqual(user.username, "alice")
        self.assertTrue(user.username.startswith("alice"))

    def test_does_not_overwrite_existing_verification_timestamp(self):
        existing = User.objects.create_user(
            username="alice_local",
            email="alice@example.com",
        )
        original = timezone.now() - timezone.timedelta(days=3)
        existing.email_verified_at = original
        existing.save(update_fields=["email_verified_at"])

        linked = get_or_create_user_from_auth0(self._userinfo())
        linked.refresh_from_db()
        self.assertEqual(linked.email_verified_at, original)

    def test_does_not_link_unverified_local_account_prevents_takeover(self):
        squatter = User.objects.create_user(
            username="squatter",
            email="alice@example.com",
            password="attacker-password",
        )
        self.assertIsNone(squatter.email_verified_at)

        owner = get_or_create_user_from_auth0(self._userinfo())

        self.assertNotEqual(owner.pk, squatter.pk)
        self.assertEqual(owner.auth0_sub, "auth0|abc123")
        self.assertIsNotNone(owner.email_verified_at)
        self.assertEqual(User.objects.filter(email__iexact="alice@example.com").count(), 2)
