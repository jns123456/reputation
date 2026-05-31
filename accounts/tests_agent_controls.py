"""Tests for account classification, agent trust/scopes, risk, and anti-abuse (§15/§16)."""

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts import abuse_services
from accounts.agent_services import (
    account_allowed_scopes,
    can_agent_write,
    can_use_scope,
    classify_account_from_onboarding,
    get_or_create_agent_profile,
)
from accounts.models import AbuseEvent, AIAgentProfile, User
from accounts.risk_services import calculate_account_risk_score, risk_band
from comments.services import cast_vote, create_comment
from comments.models import Vote
from conftest import create_market, create_user


class AccountClassificationTests(TestCase):
    def test_onboarding_maps_to_account_type(self):
        self.assertEqual(classify_account_from_onboarding("human"), User.AccountType.HUMAN)
        self.assertEqual(
            classify_account_from_onboarding("ai_assisted"), User.AccountType.HYBRID
        )
        self.assertEqual(
            classify_account_from_onboarding("autonomous_agent"),
            User.AccountType.DECLARED_AGENT,
        )
        self.assertEqual(
            classify_account_from_onboarding("organization_agent"),
            User.AccountType.ORGANIZATION_AGENT,
        )

    def test_unknown_answer_defaults_to_human(self):
        self.assertEqual(classify_account_from_onboarding("???"), User.AccountType.HUMAN)

    def test_is_ai_agent_bridge_syncs_from_account_type(self):
        user = create_user(username="bridge", account_type=User.AccountType.DECLARED_AGENT)
        self.assertTrue(user.is_ai_agent)
        self.assertTrue(user.is_agent_account)

    def test_legacy_is_ai_agent_boolean_still_promotes_account_type(self):
        user = create_user(username="legacy", is_ai_agent=True)
        self.assertEqual(user.account_type, User.AccountType.DECLARED_AGENT)


class OnboardingFlowTests(TestCase):
    def setUp(self):
        cache.clear()

    def _make_user(self):
        # A fresh user that still needs onboarding (not the conftest default).
        from django.utils import timezone

        return User.objects.create_user(
            username="newcomer",
            email="newcomer@example.com",
            password="testpass123",
            email_verified_at=timezone.now(),
            onboarding_completed=False,
        )

    def test_human_onboarding_does_not_create_agent(self):
        user = self._make_user()
        self.client.force_login(user)
        resp = self.client.post(
            reverse("accounts:profile_setup"),
            data={
                "account_operation": "human",
                "identity_mode": "public",
                "display_name": "",
                "bio": "",
            },
        )
        self.assertEqual(resp.status_code, 302)
        user.refresh_from_db()
        self.assertEqual(user.account_type, User.AccountType.HUMAN)
        self.assertFalse(user.is_ai_agent)
        self.assertFalse(AIAgentProfile.objects.filter(user=user).exists())

    def test_agent_onboarding_creates_agent_profile(self):
        user = self._make_user()
        self.client.force_login(user)
        resp = self.client.post(
            reverse("accounts:profile_setup"),
            data={
                "account_operation": "autonomous_agent",
                "agent_operator": "Acme Research",
                "agent_public_description": "Forecasts politics.",
                "identity_mode": "public",
                "display_name": "",
                "bio": "",
            },
        )
        self.assertEqual(resp.status_code, 302)
        user.refresh_from_db()
        self.assertEqual(user.account_type, User.AccountType.DECLARED_AGENT)
        profile = AIAgentProfile.objects.get(user=user)
        self.assertEqual(profile.trust_level, AIAgentProfile.TrustLevel.NEW)
        # New agents are read-only.
        self.assertNotIn("predictions:write", account_allowed_scopes(user))


class ScopeAndTrustTests(TestCase):
    def test_new_agent_is_read_only(self):
        user = create_user(username="a", account_type=User.AccountType.DECLARED_AGENT)
        get_or_create_agent_profile(user)
        self.assertFalse(can_use_scope(user, "predictions:write"))
        self.assertTrue(can_use_scope(user, "markets:read"))
        self.assertFalse(can_agent_write(user))

    def test_standard_agent_can_write(self):
        user = create_user(username="b", account_type=User.AccountType.DECLARED_AGENT)
        profile = get_or_create_agent_profile(user)
        profile.trust_level = AIAgentProfile.TrustLevel.STANDARD
        from accounts.agent_services import scopes_for_trust_level

        profile.allowed_scopes = scopes_for_trust_level(profile.trust_level)
        profile.save()
        self.assertTrue(can_agent_write(user))
        self.assertTrue(can_use_scope(user, "predictions:write"))

    def test_banned_agent_has_no_scopes(self):
        user = create_user(username="c", account_type=User.AccountType.DECLARED_AGENT)
        profile = get_or_create_agent_profile(user)
        profile.trust_level = AIAgentProfile.TrustLevel.BANNED
        profile.save()
        self.assertEqual(account_allowed_scopes(user), [])

    def test_human_account_gets_read_scopes(self):
        user = create_user(username="human")
        self.assertIn("markets:read", account_allowed_scopes(user))
        self.assertTrue(can_agent_write(user))  # humans not trust-gated


class RiskScoreTests(TestCase):
    def test_verified_old_account_is_low_risk(self):
        from datetime import timedelta

        from django.utils import timezone

        user = create_user(username="old")
        user.verification_status = User.VerificationStatus.HUMAN_CHALLENGE_PASSED
        user.save()
        User.objects.filter(pk=user.pk).update(
            created_at=timezone.now() - timedelta(days=400)
        )
        user.refresh_from_db()
        self.assertEqual(risk_band(calculate_account_risk_score(user)), "low")

    def test_suspicious_account_is_high_risk(self):
        user = create_user(username="sus", account_type=User.AccountType.SUSPICIOUS)
        user.verification_status = User.VerificationStatus.RESTRICTED
        user.email_verified_at = None
        user.save()
        self.assertEqual(risk_band(calculate_account_risk_score(user)), "high")


class AbuseControlTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_rate_limit_records_abuse_event(self):
        user = create_user(username="spammer")
        with override_settings(ABUSE_RATE_LIMITS={"comment": {"standard": (1, 3600)}}):
            abuse_services.enforce_rate_limit(action="comment", user=user, tier="standard")
            with self.assertRaises(abuse_services.RateLimitExceeded):
                abuse_services.enforce_rate_limit(action="comment", user=user, tier="standard")
        self.assertTrue(
            AbuseEvent.objects.filter(
                event_type=AbuseEvent.EventType.RATE_LIMITED, user=user
            ).exists()
        )

    def test_duplicate_content_detected(self):
        user = create_user(username="dup")
        first = abuse_services.assess_content(user=user, text="same text here please")
        second = abuse_services.assess_content(user=user, text="same text here please")
        self.assertFalse(first["is_duplicate"])
        self.assertTrue(second["is_duplicate"])

    def test_link_spam_flagged(self):
        user = create_user(username="linker")
        result = abuse_services.assess_content(
            user=user, text="http://a.com http://b.com http://c.com buy now"
        )
        self.assertIn("link_spam", result["reasons"])

    def test_circuit_breaker_trips(self):
        with override_settings(MCP_CIRCUIT_BREAKER_THRESHOLD=3):
            for _ in range(3):
                abuse_services.register_abuse_signal("mcp:submit_comment")
        self.assertTrue(abuse_services.is_circuit_open("mcp:submit_comment"))
        abuse_services.reset_circuit_breaker("mcp:submit_comment")
        self.assertFalse(abuse_services.is_circuit_open("mcp:submit_comment"))


class PopularityReputationSeparationTests(TestCase):
    """Engagement must never move predictive reputation (§6 reaffirmed in §16)."""

    def setUp(self):
        cache.clear()
        self.author = create_user(username="author")
        self.voter = create_user(username="voter")
        self.market = create_market()

    def test_voting_does_not_change_reputation(self):
        comment = create_comment(user=self.author, market=self.market, body="A real argument here")
        rep_before = self.author.profile.reputation_points
        cast_vote(
            user=self.voter,
            target_type=Vote.TargetType.COMMENT,
            target_id=comment.id,
            value=1,
        )
        self.author.profile.refresh_from_db()
        self.assertEqual(self.author.profile.reputation_points, rep_before)
        # Popularity may have moved; reputation must not.
        self.assertGreaterEqual(self.author.profile.popularity_points, 0)
