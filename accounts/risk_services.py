"""Centralized risk scoring for registration, posting, voting, and MCP calls (§16).

Returns a 0–100 score (higher = riskier) from coarse, privacy-safe signals. The
score drives rate limits, moderation queues, and trust restrictions — it is
**internal only** and must never surface private identifiers in public UI.

Kept independent of views/requests (pass primitives in) so it is unit-testable.
"""

from django.utils import timezone

# Friction thresholds — callers map score → action.
LOW_RISK_MAX = 30
MEDIUM_RISK_MAX = 70  # > MEDIUM_RISK_MAX is high risk

_SUSPICIOUS_UA_HINTS = (
    "curl",
    "wget",
    "python-requests",
    "scrapy",
    "httpclient",
    "go-http-client",
    "libwww",
)


def _account_age_days(user):
    created = getattr(user, "created_at", None) or getattr(user, "date_joined", None)
    if not created:
        return 0
    return max(0, (timezone.now() - created).days)


def calculate_account_risk_score(user) -> int:
    """Risk for an authenticated account based on age, verification, and behavior."""
    if user is None or not getattr(user, "is_authenticated", False):
        return 60

    score = 0
    age_days = _account_age_days(user)
    if age_days < 1:
        score += 25
    elif age_days < 7:
        score += 12

    if not getattr(user, "is_email_verified", False):
        score += 20

    status = getattr(user, "verification_status", "")
    if status == user.VerificationStatus.RESTRICTED:
        score += 40
    elif status in (
        user.VerificationStatus.AGENT_VERIFIED,
        user.VerificationStatus.ORGANIZATION_VERIFIED,
        user.VerificationStatus.HUMAN_CHALLENGE_PASSED,
    ):
        score -= 15

    account_type = getattr(user, "account_type", "")
    if account_type == user.AccountType.SUSPICIOUS:
        score += 50
    elif account_type == user.AccountType.UNKNOWN:
        score += 10

    # New agents are inherently higher-risk until they build history.
    agent_profile = getattr(user, "agent_profile", None)
    if agent_profile is not None:
        if agent_profile.trust_level == agent_profile.TrustLevel.BANNED:
            score += 60
        elif agent_profile.trust_level in (
            agent_profile.TrustLevel.NEW,
            agent_profile.TrustLevel.LIMITED,
            agent_profile.TrustLevel.RESTRICTED,
        ):
            score += 15
        elif agent_profile.trust_level == agent_profile.TrustLevel.TRUSTED:
            score -= 10

    # Recent abuse history.
    try:
        recent_abuse = user.abuse_events.count()
    except Exception:  # noqa: BLE001
        recent_abuse = 0
    score += min(recent_abuse * 5, 30)

    return max(0, min(score, 100))


def calculate_request_risk_score(
    *,
    user=None,
    ip=None,
    user_agent="",
    content=None,
    failed_attempts=0,
    duplicate_identifier=False,
    is_human_verified=None,
):
    """Risk for a single request/action; combines account + request signals."""
    score = 0
    if user is not None and getattr(user, "is_authenticated", False):
        score += int(calculate_account_risk_score(user) * 0.6)
    else:
        score += 40  # anonymous requests start moderately risky

    ua = (user_agent or "").lower()
    if not ua:
        score += 10
    elif any(hint in ua for hint in _SUSPICIOUS_UA_HINTS):
        score += 20

    if failed_attempts:
        score += min(failed_attempts * 8, 40)

    if duplicate_identifier:
        score += 25

    if content:
        from accounts.abuse_services import content_fingerprint, link_count

        if link_count(content) >= 3:
            score += 15
        if len(content.strip()) <= 3:
            score += 10
        # Fingerprint is computed to keep the signal available to callers/logs.
        _ = content_fingerprint(content)

    if is_human_verified is False:
        score += 20
    elif is_human_verified is True:
        score -= 15

    return max(0, min(score, 100))


def risk_band(score):
    if score <= LOW_RISK_MAX:
        return "low"
    if score <= MEDIUM_RISK_MAX:
        return "medium"
    return "high"
