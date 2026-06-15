"""Account classification, agent trust, and scope authorization (§15).

Single source of truth for:
- mapping an onboarding self-declaration → ``User.account_type``
- which MCP/API scopes an account is allowed to use (read vs write)
- whether an agent's trust level permits a given write

The MCP layer (§17) and any future API auth call these helpers — they must not
re-derive scopes independently.
"""

from accounts.models import AIAgentProfile, User

# Canonical scope vocabulary (also used by the MCP registry, §17).
READ_SCOPES = (
    "markets:read",
    "reputation:read",
    "popularity:read",
)
WRITE_SCOPES = (
    "predictions:write",
    "comments:write",
    "votes:write",
    "social:write",
    "forum:write",
    "challenges:write",
)
ALL_SCOPES = READ_SCOPES + WRITE_SCOPES

# Onboarding answer → account type.
OPERATION_MODE_TO_ACCOUNT_TYPE = {
    "human": User.AccountType.HUMAN,
    "ai_assisted": User.AccountType.HYBRID,
    "autonomous_agent": User.AccountType.DECLARED_AGENT,
    "organization_agent": User.AccountType.ORGANIZATION_AGENT,
}

# Scopes granted by trust level. New/limited agents are strictly read-only.
TRUST_LEVEL_SCOPES = {
    AIAgentProfile.TrustLevel.NEW: list(READ_SCOPES),
    AIAgentProfile.TrustLevel.LIMITED: list(READ_SCOPES),
    AIAgentProfile.TrustLevel.STANDARD: list(READ_SCOPES) + list(WRITE_SCOPES),
    AIAgentProfile.TrustLevel.TRUSTED: list(ALL_SCOPES),
    AIAgentProfile.TrustLevel.RESTRICTED: [],
    AIAgentProfile.TrustLevel.BANNED: [],
}


def classify_account_from_onboarding(operation_mode):
    """Map an onboarding operation-mode answer to an account type.

    Unknown/blank answers fall back to ``human`` (the safe default — we never
    force a person into agent status; AGENTS.md §15).
    """
    return OPERATION_MODE_TO_ACCOUNT_TYPE.get(operation_mode, User.AccountType.HUMAN)


def requires_agent_disclosure(account_type):
    """Primarily AI-controlled accounts must disclose an operator/agent profile."""
    return account_type in (
        User.AccountType.DECLARED_AGENT,
        User.AccountType.ORGANIZATION_AGENT,
    )


def apply_account_classification(user, *, operation_mode, save=True):
    """Set ``account_type`` from an onboarding answer and return it."""
    account_type = classify_account_from_onboarding(operation_mode)
    user.account_type = account_type
    if save:
        user.save(update_fields=["account_type", "is_ai_agent", "updated_at"])
    return account_type


def get_or_create_agent_profile(user, **defaults):
    """Ensure an AIAgentProfile exists for an agent account.

    New profiles start at ``trust_level=new`` with read-only scopes — write
    permissions are earned progressively (§15).
    """
    defaults.setdefault("agent_name", user.display_name or user.username)
    if user.account_type == User.AccountType.ORGANIZATION_AGENT:
        defaults.setdefault("operator_type", AIAgentProfile.OperatorType.COMPANY)
    profile, created = AIAgentProfile.objects.get_or_create(
        user=user,
        defaults=defaults,
    )
    if created and not profile.allowed_scopes:
        profile.allowed_scopes = scopes_for_trust_level(profile.trust_level)
        profile.save(update_fields=["allowed_scopes", "updated_at"])
    return profile


def scopes_for_trust_level(trust_level):
    return list(TRUST_LEVEL_SCOPES.get(trust_level, list(READ_SCOPES)))


def agent_allowed_scopes(user):
    """Effective scopes for an account.

    Humans get read scopes by default. Agents are bounded by BOTH their
    explicitly granted ``allowed_scopes`` and what their trust level permits
    (the intersection) so an admin lowering trust immediately revokes writes.
    """
    agent_profile = getattr(user, "agent_profile", None)
    if agent_profile is None:
        return list(READ_SCOPES)
    if agent_profile.trust_level == AIAgentProfile.TrustLevel.BANNED:
        return []
    trust_scopes = set(scopes_for_trust_level(agent_profile.trust_level))
    granted = set(agent_profile.allowed_scopes or [])
    if not granted:
        granted = set(READ_SCOPES)
    # Read scopes are always allowed (unless restricted/banned removes them).
    effective = (granted | set(READ_SCOPES)) & (trust_scopes | set(READ_SCOPES))
    if agent_profile.trust_level == AIAgentProfile.TrustLevel.RESTRICTED:
        effective &= set(READ_SCOPES)
    return sorted(effective)


def account_allowed_scopes(user):
    """Scopes for any account (delegates to agent logic when applicable).

    Human accounts may mint tokens with full read/write scopes for REST/MCP
    integrations; agent accounts remain trust-gated (§15).
    """
    if getattr(user, "is_agent_account", False) or getattr(user, "agent_profile", None):
        return agent_allowed_scopes(user)
    return list(ALL_SCOPES)


def is_write_scope(scope):
    return scope in WRITE_SCOPES


def can_use_scope(user, scope):
    """Whether ``user`` may use ``scope`` right now."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    allowed = account_allowed_scopes(user)
    if scope not in allowed:
        return False
    if is_write_scope(scope):
        return can_agent_write(user)
    return True


def can_agent_write(user):
    """Trust-gate for write actions.

    Non-agent (human) accounts are allowed (their writes go through the normal
    rate limits/spam checks). Agent accounts must be at least ``standard`` trust.
    """
    agent_profile = getattr(user, "agent_profile", None)
    if agent_profile is None:
        return True
    return agent_profile.can_write
