"""Tests for trust promotion, moderation queue, and signup human verification."""

from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import AbuseEvent, AIAgentProfile, User
from accounts.moderation_services import bulk_moderate
from accounts.trust_services import (
    count_useful_contributions,
    evaluate_agent_trust,
    promote_eligible_agents,
)
from comments.models import Comment
from conftest import create_market, create_user


def _make_agent(username, trust=AIAgentProfile.TrustLevel.NEW, age_days=0):
    user = create_user(username=username, account_type=User.AccountType.DECLARED_AGENT)
    if age_days:
        created = timezone.now() - timedelta(days=age_days)
        User.objects.filter(pk=user.pk).update(created_at=created)
        user.refresh_from_db()
    profile = AIAgentProfile.objects.create(
        user=user,
        agent_name=username,
        trust_level=trust,
        rate_limit_tier="new",
        allowed_scopes=["markets:read"],
    )
    return user, profile


class TrustPromotionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.market = create_market()

    def _add_contributions(self, user, n):
        for i in range(n):
            Comment.objects.create(user=user, market=self.market, body=f"reasoning {i}")

    def test_new_agent_without_history_stays_new(self):
        _user, profile = _make_agent("fresh", age_days=0)
        self.assertEqual(evaluate_agent_trust(profile), AIAgentProfile.TrustLevel.NEW)

    def test_aged_verified_agent_reaches_limited(self):
        _user, profile = _make_agent("aged", age_days=2)
        self.assertEqual(evaluate_agent_trust(profile), AIAgentProfile.TrustLevel.LIMITED)

    def test_contributing_agent_reaches_standard(self):
        user, profile = _make_agent("worker", age_days=10)
        self._add_contributions(user, 6)
        self.assertEqual(count_useful_contributions(user), 6)
        self.assertEqual(evaluate_agent_trust(profile), AIAgentProfile.TrustLevel.STANDARD)

    def test_recent_high_abuse_forces_restricted(self):
        user, profile = _make_agent("bad", trust=AIAgentProfile.TrustLevel.STANDARD, age_days=40)
        self._add_contributions(user, 30)
        for _ in range(3):
            AbuseEvent.objects.create(
                user=user,
                event_type=AbuseEvent.EventType.SPAM_SUSPECTED,
                severity=AbuseEvent.Severity.HIGH,
                scope="comment",
            )
        self.assertEqual(evaluate_agent_trust(profile), AIAgentProfile.TrustLevel.RESTRICTED)

    def test_promotion_never_demotes_trusted_agent(self):
        _user, profile = _make_agent("vip", trust=AIAgentProfile.TrustLevel.TRUSTED, age_days=0)
        self.assertEqual(evaluate_agent_trust(profile), AIAgentProfile.TrustLevel.TRUSTED)

    def test_promote_eligible_agents_applies_changes(self):
        user, profile = _make_agent("ladder", age_days=10)
        self._add_contributions(user, 6)
        summary = promote_eligible_agents()
        profile.refresh_from_db()
        self.assertEqual(profile.trust_level, AIAgentProfile.TrustLevel.STANDARD)
        self.assertIn("predictions:write", profile.allowed_scopes)
        self.assertGreaterEqual(summary["promotions"], 1)

    def test_promotion_syncs_rate_limit_tier(self):
        user, profile = _make_agent("tiered", age_days=10)
        self._add_contributions(user, 6)
        promote_eligible_agents()
        profile.refresh_from_db()
        self.assertEqual(profile.rate_limit_tier, AIAgentProfile.RateLimitTier.STANDARD)


class ModerationServiceTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_bulk_restrict_agent(self):
        user, profile = _make_agent("r", trust=AIAgentProfile.TrustLevel.STANDARD)
        affected = bulk_moderate(action="restrict", user_ids=[user.id])
        profile.refresh_from_db()
        self.assertEqual(affected, 1)
        self.assertEqual(profile.trust_level, AIAgentProfile.TrustLevel.RESTRICTED)

    def test_bulk_ban_agent(self):
        user, profile = _make_agent("b", trust=AIAgentProfile.TrustLevel.STANDARD)
        bulk_moderate(action="ban", user_ids=[user.id])
        profile.refresh_from_db()
        self.assertEqual(profile.trust_level, AIAgentProfile.TrustLevel.BANNED)
        self.assertEqual(profile.allowed_scopes, [])

    def test_bulk_verify_agent(self):
        user, profile = _make_agent("v")
        bulk_moderate(action="verify", user_ids=[user.id])
        profile.refresh_from_db()
        self.assertTrue(profile.is_verified_agent)

    def test_clear_suspicious_user(self):
        user = create_user(username="sus", account_type=User.AccountType.SUSPICIOUS)
        bulk_moderate(action="clear_suspicious", user_ids=[user.id])
        user.refresh_from_db()
        self.assertEqual(user.account_type, User.AccountType.HUMAN)

    def test_moderation_action_records_audit_event(self):
        user, _profile = _make_agent("audit", trust=AIAgentProfile.TrustLevel.STANDARD)
        bulk_moderate(action="restrict", user_ids=[user.id])
        self.assertTrue(
            AbuseEvent.objects.filter(
                user=user, event_type=AbuseEvent.EventType.MODERATION_ACTION
            ).exists()
        )

    def test_invalid_action_is_noop(self):
        user, _profile = _make_agent("noop")
        self.assertEqual(bulk_moderate(action="explode", user_ids=[user.id]), 0)


class ModerationQueueViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = create_user(username="boss")
        User.objects.filter(pk=self.admin.pk).update(is_superuser=True, is_staff=True)
        self.admin.refresh_from_db()
        self.client.force_login(self.admin)

    def test_queue_renders_for_superadmin(self):
        resp = self.client.get(reverse("dashboard:moderation_queue"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Moderation queue")

    def test_non_admin_blocked(self):
        plain = create_user(username="plain")
        self.client.force_login(plain)
        resp = self.client.get(reverse("dashboard:moderation_queue"))
        self.assertNotEqual(resp.status_code, 200)

    def test_action_endpoint_applies_moderation(self):
        user, profile = _make_agent("target", trust=AIAgentProfile.TrustLevel.STANDARD)
        resp = self.client.post(
            reverse("dashboard:moderation_action"),
            {"action": "restrict", "user_ids": [user.id]},
        )
        self.assertEqual(resp.status_code, 302)
        profile.refresh_from_db()
        self.assertEqual(profile.trust_level, AIAgentProfile.TrustLevel.RESTRICTED)


class SignupHumanVerificationTests(TestCase):
    def setUp(self):
        cache.clear()

    @override_settings(HUMAN_VERIFICATION_PROVIDER="noop", HUMAN_VERIFICATION_REQUIRED=False)
    def test_signup_succeeds_with_noop_provider(self):
        resp = self.client.post(
            reverse("accounts:signup"),
            {
                "username": "joiner",
                "email": "joiner@example.com",
                "password1": "Str0ngP@ssw0rd!2x",
                "password2": "Str0ngP@ssw0rd!2x",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(User.objects.filter(username="joiner").exists())

    @override_settings(
        HUMAN_VERIFICATION_PROVIDER="turnstile",
        HUMAN_VERIFICATION_REQUIRED=True,
        TURNSTILE_SECRET_KEY="",
    )
    def test_signup_blocked_when_verification_required_and_missing(self):
        resp = self.client.post(
            reverse("accounts:signup"),
            {
                "username": "botter",
                "email": "botter@example.com",
                "password1": "Str0ngP@ssw0rd!2x",
                "password2": "Str0ngP@ssw0rd!2x",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username="botter").exists())
        self.assertTrue(
            AbuseEvent.objects.filter(
                event_type=AbuseEvent.EventType.REGISTRATION_RISK
            ).exists()
        )
