"""Anti-abuse controls: rate limits, duplicate detection, circuit breakers (§16).

Centralized here so views, the DRF API, and the MCP layer (§17) share one set of
limits and one audit trail (``AbuseEvent``). Limits are cache-backed (Redis in
prod, LocMem in dev/test) using fixed windows — simple and sufficient without extra infrastructure.
"""

import hashlib
import re

from django.conf import settings
from django.core.cache import cache

from accounts.models import AbuseEvent

# (limit, window_seconds) per action, keyed by rate-limit tier.
DEFAULT_RATE_LIMITS = {
    "comment": {
        "new": (5, 3600),
        "standard": (40, 3600),
        "trusted": (200, 3600),
        "throttled": (2, 3600),
    },
    "post": {
        "new": (5, 3600),
        "standard": (40, 3600),
        "trusted": (200, 3600),
        "throttled": (2, 3600),
    },
    "prediction": {
        "new": (10, 3600),
        "standard": (60, 3600),
        "trusted": (300, 3600),
        "throttled": (3, 3600),
    },
    "debrief": {
        "new": (10, 3600),
        "standard": (40, 3600),
        "trusted": (200, 3600),
        "throttled": (2, 3600),
    },
    "vote": {
        "new": (60, 3600),
        "standard": (300, 3600),
        "trusted": (1000, 3600),
        "throttled": (20, 3600),
    },
    "follow": {
        "new": (30, 3600),
        "standard": (150, 3600),
        "trusted": (500, 3600),
        "throttled": (10, 3600),
    },
    "creator_subscribe": {
        "new": (20, 3600),
        "standard": (80, 3600),
        "trusted": (200, 3600),
        "throttled": (5, 3600),
    },
    "message": {
        "new": (20, 3600),
        "standard": (120, 3600),
        "trusted": (500, 3600),
        "throttled": (10, 3600),
    },
    "registration": {  # keyed by IP, tier is always "ip"
        "ip": (5, 3600),
    },
    "login": {
        "ip": (20, 900),
    },
    "account_deletion": {
        "ip": (5, 3600),
    },
    "password_reset": {
        "ip": (5, 3600),
    },
    "mcp_http": {
        "ip": (300, 3600),
    },
    "mcp_call": {
        "new": (60, 3600),
        "standard": (600, 3600),
        "trusted": (3000, 3600),
        "throttled": (20, 3600),
    },
    "mcp_write": {
        "new": (10, 3600),
        "standard": (60, 3600),
        "trusted": (300, 3600),
        "throttled": (2, 3600),
    },
}


class RateLimitExceeded(Exception):
    """Raised when an action exceeds its allowed rate."""

    def __init__(self, action, retry_after=None):
        self.action = action
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded for '{action}'.")


def _rate_limits():
    overrides = getattr(settings, "ABUSE_RATE_LIMITS", None) or {}
    merged = {k: dict(v) for k, v in DEFAULT_RATE_LIMITS.items()}
    for action, tiers in overrides.items():
        merged.setdefault(action, {}).update(tiers)
    return merged


def get_rate_limit_tier(user):
    """Pick a rate-limit tier for a user (agents use their profile's tier)."""
    if user is None or not getattr(user, "is_authenticated", False):
        return "new"
    agent_profile = getattr(user, "agent_profile", None)
    if agent_profile is not None:
        tier = agent_profile.rate_limit_tier
        return tier if tier in ("new", "standard", "trusted", "throttled") else "new"
    from django.utils import timezone

    if getattr(user, "verification_status", "") == user.VerificationStatus.RESTRICTED:
        return "throttled"
    created = getattr(user, "created_at", None) or getattr(user, "date_joined", None)
    is_new = created is not None and (timezone.now() - created).days < 3
    if is_new and not getattr(user, "is_email_verified", False):
        return "new"
    return "standard"


def _resolve_limit(action, tier):
    rules = _rate_limits().get(action, {})
    if not rules:
        return None
    if tier in rules:
        return rules[tier]
    # IP-keyed actions store a single "ip" bucket.
    if "ip" in rules:
        return rules["ip"]
    return rules.get("standard") or next(iter(rules.values()))


def check_rate_limit(*, action, identifier, tier="standard"):
    """Return (allowed: bool, info: dict). Increments the window counter."""
    limit_conf = _resolve_limit(action, tier)
    if not limit_conf:
        return True, {"unlimited": True}
    limit, window = limit_conf
    cache_key = f"rl:{action}:{tier}:{identifier}"
    count = cache.get(cache_key)
    if count is None:
        cache.set(cache_key, 1, timeout=window)
        count = 1
    else:
        try:
            count = cache.incr(cache_key)
        except ValueError:
            cache.set(cache_key, 1, timeout=window)
            count = 1
    allowed = count <= limit
    return allowed, {"count": count, "limit": limit, "window": window}


def enforce_rate_limit(*, action, user=None, identifier=None, tier=None, record=True):
    """Raise RateLimitExceeded when over the limit; record an AbuseEvent.

    ``identifier`` defaults to the user id. For IP-keyed actions
    (registration/login) pass the IP explicitly.
    """
    if tier is None:
        tier = get_rate_limit_tier(user)
    if identifier is None:
        identifier = f"user:{getattr(user, 'id', 'anon')}"
    allowed, info = check_rate_limit(action=action, identifier=identifier, tier=tier)
    if not allowed:
        if record:
            record_abuse_event(
                user=user if getattr(user, "is_authenticated", False) else None,
                event_type=AbuseEvent.EventType.RATE_LIMITED,
                severity=AbuseEvent.Severity.MEDIUM,
                scope=action,
                action_taken="throttled",
                reason=f"Rate limit exceeded for '{action}' (tier={tier}).",
                signals={k: v for k, v in info.items() if k != "unlimited"},
            )
        raise RateLimitExceeded(action, retry_after=info.get("window"))
    return info


def record_abuse_event(
    *,
    user=None,
    event_type,
    severity=AbuseEvent.Severity.LOW,
    scope="",
    risk_score=0,
    action_taken="",
    reason="",
    signals=None,
):
    """Append an immutable AbuseEvent. Best-effort — never raises into callers."""
    try:
        return AbuseEvent.objects.create(
            user=user,
            event_type=event_type,
            severity=severity,
            scope=scope,
            risk_score=risk_score,
            action_taken=action_taken,
            reason=reason,
            signals=signals or {},
        )
    except Exception:  # noqa: BLE001 - auditing must not break the request
        return None


# --- Duplicate / spam content detection -------------------------------------

_DUPLICATE_WINDOW = 6 * 3600
_URL_RE = re.compile(r"https?://", re.IGNORECASE)


def _normalize_text(text):
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def content_fingerprint(text):
    return hashlib.sha256(_normalize_text(text).encode("utf-8")).hexdigest()


def is_duplicate_content(*, user, text, scope="comment"):
    """True when the user posted identical (normalized) content recently."""
    if not text or user is None or not getattr(user, "is_authenticated", False):
        return False
    fp = content_fingerprint(text)
    cache_key = f"dup:{scope}:{user.id}:{fp}"
    if cache.get(cache_key):
        return True
    cache.set(cache_key, 1, timeout=_DUPLICATE_WINDOW)
    return False


def link_count(text):
    return len(_URL_RE.findall(text or ""))


def assess_content(*, user, text, scope="comment"):
    """Lightweight spam assessment for user/agent-submitted text.

    Returns a dict: {is_spam, is_duplicate, reasons, risk_score}. Records an
    AbuseEvent when something is flagged. Callers decide whether to block or
    quarantine based on ``is_spam``.
    """
    reasons = []
    risk = 0
    normalized = _normalize_text(text)
    is_direct_message = scope.startswith("write:message:")

    is_dup = False
    if not is_direct_message:
        is_dup = is_duplicate_content(user=user, text=text, scope=scope)
        if is_dup:
            reasons.append("duplicate")
            risk += 50

    links = link_count(text)
    if links >= 3:
        reasons.append("link_spam")
        risk += 30

    if not is_direct_message and normalized and len(normalized) <= 3:
        reasons.append("too_short")
        risk += 10

    # Mostly-repeated single token, e.g. "buy buy buy buy".
    tokens = normalized.split()
    if len(tokens) >= 5 and len(set(tokens)) <= 2:
        reasons.append("repetitive")
        risk += 30

    is_spam = risk >= 50
    if reasons:
        record_abuse_event(
            user=user if getattr(user, "is_authenticated", False) else None,
            event_type=(
                AbuseEvent.EventType.DUPLICATE_CONTENT
                if is_dup
                else AbuseEvent.EventType.SPAM_SUSPECTED
            ),
            severity=(
                AbuseEvent.Severity.MEDIUM if is_spam else AbuseEvent.Severity.LOW
            ),
            scope=scope,
            risk_score=min(risk, 100),
            action_taken="blocked" if is_spam else "flagged",
            reason=", ".join(reasons),
        )
    return {
        "is_spam": is_spam,
        "is_duplicate": is_dup,
        "reasons": reasons,
        "risk_score": min(risk, 100),
    }


# --- Circuit breaker (MCP write tools) ---------------------------------------

_BREAKER_KEY = "circuit_breaker:{name}"


def _breaker_threshold():
    return getattr(settings, "MCP_CIRCUIT_BREAKER_THRESHOLD", 25)


def _breaker_window():
    return getattr(settings, "MCP_CIRCUIT_BREAKER_WINDOW_SECONDS", 300)


def register_abuse_signal(name):
    """Increment the abuse counter for a named circuit (e.g. an MCP write tool)."""
    key = f"abuse_signal:{name}"
    count = cache.get(key)
    if count is None:
        cache.set(key, 1, timeout=_breaker_window())
        count = 1
    else:
        try:
            count = cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=_breaker_window())
            count = 1
    if count >= _breaker_threshold():
        trip_circuit_breaker(name)
    return count


def trip_circuit_breaker(name):
    cache.set(_BREAKER_KEY.format(name=name), 1, timeout=_breaker_window())
    record_abuse_event(
        event_type=AbuseEvent.EventType.CIRCUIT_BREAKER,
        severity=AbuseEvent.Severity.HIGH,
        scope=name,
        action_taken="disabled",
        reason=f"Circuit breaker tripped for '{name}' — abuse signals exceeded threshold.",
    )


def is_circuit_open(name):
    """True when the named circuit is tripped (the protected action is disabled)."""
    return bool(cache.get(_BREAKER_KEY.format(name=name)))


def reset_circuit_breaker(name):
    cache.delete(_BREAKER_KEY.format(name=name))
    cache.delete(f"abuse_signal:{name}")
