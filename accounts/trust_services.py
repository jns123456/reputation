"""Automatic agent trust promotion (AGENTS.md §15).

Replaces manual admin promotion with an auditable, rule-based evaluation:
agents earn higher trust (and thus write scopes + higher rate limits) through
account age, verification, useful contribution history, and a clean abuse record.

Auto-promotion only moves agents *up* the new→limited→standard→trusted ladder;
it never silently demotes a manually-trusted agent. Repeated high-severity abuse
is the one downward path (→ restricted). Banned/restricted agents are left to
admins (and the circuit breaker, §16).
"""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from accounts.agent_services import scopes_for_trust_level
from accounts.models import AbuseEvent, AIAgentProfile

# Ordered ladder used to avoid auto-demotion.
_LADDER = [
    AIAgentProfile.TrustLevel.NEW,
    AIAgentProfile.TrustLevel.LIMITED,
    AIAgentProfile.TrustLevel.STANDARD,
    AIAgentProfile.TrustLevel.TRUSTED,
]
_LADDER_RANK = {level: i for i, level in enumerate(_LADDER)}

_RATE_TIER_FOR_TRUST = {
    AIAgentProfile.TrustLevel.NEW: AIAgentProfile.RateLimitTier.NEW,
    AIAgentProfile.TrustLevel.LIMITED: AIAgentProfile.RateLimitTier.NEW,
    AIAgentProfile.TrustLevel.STANDARD: AIAgentProfile.RateLimitTier.STANDARD,
    AIAgentProfile.TrustLevel.TRUSTED: AIAgentProfile.RateLimitTier.TRUSTED,
    AIAgentProfile.TrustLevel.RESTRICTED: AIAgentProfile.RateLimitTier.THROTTLED,
    AIAgentProfile.TrustLevel.BANNED: AIAgentProfile.RateLimitTier.THROTTLED,
}


def _thresholds():
    return {
        "limited_age_days": getattr(settings, "AGENT_TRUST_LIMITED_AGE_DAYS", 1),
        "standard_age_days": getattr(settings, "AGENT_TRUST_STANDARD_AGE_DAYS", 7),
        "standard_contributions": getattr(settings, "AGENT_TRUST_STANDARD_CONTRIBUTIONS", 5),
        "trusted_age_days": getattr(settings, "AGENT_TRUST_TRUSTED_AGE_DAYS", 30),
        "trusted_contributions": getattr(settings, "AGENT_TRUST_TRUSTED_CONTRIBUTIONS", 25),
        "abuse_block": getattr(settings, "AGENT_TRUST_ABUSE_BLOCK", 3),
        "abuse_window_days": getattr(settings, "AGENT_TRUST_ABUSE_WINDOW_DAYS", 7),
    }


def _account_age_days(user):
    created = getattr(user, "created_at", None) or getattr(user, "date_joined", None)
    if not created:
        return 0
    return max(0, (timezone.now() - created).days)


def count_useful_contributions(user):
    """Predictions made + comments posted — a coarse 'did real work' signal."""
    from comments.models import Comment

    predictions = user.predictions.count()
    comments = Comment.objects.filter(user=user).count()
    return predictions + comments


def _recent_high_severity_abuse(user, *, window_days):
    cutoff = timezone.now() - timedelta(days=window_days)
    return AbuseEvent.objects.filter(
        user=user,
        severity=AbuseEvent.Severity.HIGH,
        created_at__gte=cutoff,
    ).count()


def evaluate_agent_trust(profile):
    """Return the recommended trust level for an agent profile (no side effects)."""
    if profile.trust_level == AIAgentProfile.TrustLevel.BANNED:
        return AIAgentProfile.TrustLevel.BANNED

    t = _thresholds()
    user = profile.user

    if _recent_high_severity_abuse(user, window_days=t["abuse_window_days"]) >= t["abuse_block"]:
        return AIAgentProfile.TrustLevel.RESTRICTED

    # An admin-set RESTRICTED state is not auto-cleared here.
    if profile.trust_level == AIAgentProfile.TrustLevel.RESTRICTED:
        return AIAgentProfile.TrustLevel.RESTRICTED

    age = _account_age_days(user)
    contributions = count_useful_contributions(user)
    email_verified = getattr(user, "is_email_verified", False)

    eligible = AIAgentProfile.TrustLevel.NEW
    if email_verified and age >= t["limited_age_days"]:
        eligible = AIAgentProfile.TrustLevel.LIMITED
    if (
        email_verified
        and age >= t["standard_age_days"]
        and contributions >= t["standard_contributions"]
    ):
        eligible = AIAgentProfile.TrustLevel.STANDARD
    if (
        email_verified
        and age >= t["trusted_age_days"]
        and contributions >= t["trusted_contributions"]
    ):
        eligible = AIAgentProfile.TrustLevel.TRUSTED

    # Never auto-demote within the upward ladder.
    current_rank = _LADDER_RANK.get(profile.trust_level, -1)
    eligible_rank = _LADDER_RANK.get(eligible, 0)
    if current_rank > eligible_rank:
        return profile.trust_level
    return eligible


def apply_trust_level(profile, trust_level, *, sync_scopes=True):
    """Persist a trust-level change and keep tier + scopes consistent."""
    changed_fields = []
    if profile.trust_level != trust_level:
        profile.trust_level = trust_level
        changed_fields.append("trust_level")
    new_tier = _RATE_TIER_FOR_TRUST.get(trust_level, profile.rate_limit_tier)
    if profile.rate_limit_tier != new_tier:
        profile.rate_limit_tier = new_tier
        changed_fields.append("rate_limit_tier")
    if sync_scopes:
        new_scopes = scopes_for_trust_level(trust_level)
        if profile.allowed_scopes != new_scopes:
            profile.allowed_scopes = new_scopes
            changed_fields.append("allowed_scopes")
    if changed_fields:
        changed_fields.append("updated_at")
        profile.save(update_fields=changed_fields)
    return bool(changed_fields)


def promote_eligible_agents(*, limit=None):
    """Evaluate all agent profiles and apply recommended trust changes.

    Returns a summary dict: {evaluated, changed, promotions, restrictions}.
    """
    qs = AIAgentProfile.objects.exclude(
        trust_level=AIAgentProfile.TrustLevel.BANNED
    ).select_related("user")
    if limit:
        qs = qs[:limit]

    evaluated = changed = promotions = restrictions = 0
    for profile in qs:
        evaluated += 1
        recommended = evaluate_agent_trust(profile)
        if recommended == profile.trust_level:
            continue
        was_rank = _LADDER_RANK.get(profile.trust_level, -1)
        now_rank = _LADDER_RANK.get(recommended, -1)
        if apply_trust_level(profile, recommended):
            changed += 1
            if recommended == AIAgentProfile.TrustLevel.RESTRICTED:
                restrictions += 1
            elif now_rank > was_rank:
                promotions += 1
    return {
        "evaluated": evaluated,
        "changed": changed,
        "promotions": promotions,
        "restrictions": restrictions,
    }
