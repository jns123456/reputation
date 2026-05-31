"""Admin moderation actions for agents and suspicious accounts (AGENTS.md §16).

Thin, auditable operations used by the moderation queue. Each bulk action
records an ``AbuseEvent`` of type ``moderation_action`` so the trail is complete.
"""

from accounts.abuse_services import record_abuse_event
from accounts.models import AbuseEvent, AIAgentProfile, User
from accounts.trust_services import apply_trust_level, evaluate_agent_trust

AGENT_ACTIONS = {"restrict", "ban", "verify", "promote", "reset_standard"}
USER_ACTIONS = {"clear_suspicious", "mark_suspicious"}
VALID_ACTIONS = AGENT_ACTIONS | USER_ACTIONS


def _record(user, action, reason):
    record_abuse_event(
        user=user,
        event_type=AbuseEvent.EventType.MODERATION_ACTION,
        severity=AbuseEvent.Severity.INFO,
        scope="moderation",
        action_taken=action,
        reason=reason,
    )


def moderate_agent(profile, action):
    if action == "restrict":
        apply_trust_level(profile, AIAgentProfile.TrustLevel.RESTRICTED)
    elif action == "ban":
        apply_trust_level(profile, AIAgentProfile.TrustLevel.BANNED)
    elif action == "verify":
        profile.is_verified_agent = True
        profile.save(update_fields=["is_verified_agent", "updated_at"])
    elif action == "reset_standard":
        apply_trust_level(profile, AIAgentProfile.TrustLevel.STANDARD)
    elif action == "promote":
        apply_trust_level(profile, evaluate_agent_trust(profile))
    else:
        return False
    _record(profile.user, action, f"Agent moderation: {action}.")
    return True


def moderate_user(user, action):
    if action == "clear_suspicious":
        if user.account_type == User.AccountType.SUSPICIOUS:
            user.account_type = User.AccountType.HUMAN
        if user.verification_status == User.VerificationStatus.RESTRICTED:
            user.verification_status = User.VerificationStatus.UNVERIFIED
        user.save(update_fields=["account_type", "verification_status", "is_ai_agent", "updated_at"])
    elif action == "mark_suspicious":
        user.account_type = User.AccountType.SUSPICIOUS
        user.verification_status = User.VerificationStatus.RESTRICTED
        user.save(update_fields=["account_type", "verification_status", "is_ai_agent", "updated_at"])
    else:
        return False
    _record(user, action, f"User moderation: {action}.")
    return True


def bulk_moderate(*, action, user_ids):
    """Apply a moderation action to many accounts. Returns count affected."""
    if action not in VALID_ACTIONS or not user_ids:
        return 0
    affected = 0
    if action in AGENT_ACTIONS:
        profiles = AIAgentProfile.objects.filter(user_id__in=user_ids).select_related("user")
        for profile in profiles:
            if moderate_agent(profile, action):
                affected += 1
    else:
        users = User.objects.filter(id__in=user_ids)
        for user in users:
            if moderate_user(user, action):
                affected += 1
    return affected
