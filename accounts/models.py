from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy


class User(AbstractUser):
    class IdentityMode(models.TextChoices):
        PUBLIC = "public", _lazy("Public")
        PSEUDONYM = "pseudonym", _lazy("Pseudonym")
        ANONYMOUS = "anonymous", _lazy("Anonymous")

    class AccountType(models.TextChoices):
        HUMAN = "human", _lazy("Human")
        DECLARED_AGENT = "declared_agent", _lazy("Declared AI agent")
        ORGANIZATION_AGENT = "organization_agent", _lazy("Organization AI agent")
        HYBRID = "hybrid", _lazy("Human + AI assisted")
        UNKNOWN = "unknown", _lazy("Unknown")
        SUSPICIOUS = "suspicious", _lazy("Suspicious")

    class VerificationStatus(models.TextChoices):
        UNVERIFIED = "unverified", _lazy("Unverified")
        EMAIL_VERIFIED = "email_verified", _lazy("Email verified")
        HUMAN_CHALLENGE_PASSED = "human_challenge_passed", _lazy("Human challenge passed")
        AGENT_VERIFIED = "agent_verified", _lazy("Agent verified")
        ORGANIZATION_VERIFIED = "organization_verified", _lazy("Organization verified")
        RESTRICTED = "restricted", _lazy("Restricted")

    # Operating-mode classification (AGENTS.md §15). ``is_ai_agent`` below is a
    # derived backward-compatibility bridge kept in sync via ``save()``.
    account_type = models.CharField(
        max_length=20,
        choices=AccountType.choices,
        default=AccountType.HUMAN,
        db_index=True,
        help_text="How the account is primarily operated (human vs AI agent).",
    )
    verification_status = models.CharField(
        max_length=30,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNVERIFIED,
        db_index=True,
        help_text="Progressive verification/anti-abuse status for the account.",
    )
    display_name = models.CharField(max_length=150, blank=True)
    identity_mode = models.CharField(
        max_length=20,
        choices=IdentityMode.choices,
        default=IdentityMode.PUBLIC,
        help_text="How the user appears publicly on the platform.",
    )
    hide_from_user_directory = models.BooleanField(
        default=False,
        help_text="When true, the account is omitted from the public user list and search.",
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Platform-verified identity (admin-granted).",
    )
    verification_requested = models.BooleanField(
        default=False,
        help_text="User requested identity verification review.",
    )
    onboarding_completed = models.BooleanField(
        default=False,
        help_text="Whether the user finished first-time profile and identity setup.",
    )
    email_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the user confirmed ownership of their email address.",
    )
    is_ai_agent = models.BooleanField(default=False)
    auth0_sub = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
        help_text="Auth0 subject identifier (sub claim) when the account is linked to Auth0.",
    )
    bio = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    AGENT_ACCOUNT_TYPES = (
        AccountType.DECLARED_AGENT,
        AccountType.ORGANIZATION_AGENT,
    )

    class Meta:
        ordering = ["username"]

    def save(self, *args, **kwargs):
        # Bidirectional bridge between the rich classification and the legacy
        # boolean (AGENTS.md §15) so both old code paths (that set ``is_ai_agent``
        # directly) and new code (that set ``account_type``) stay consistent.
        if self.account_type in self.AGENT_ACCOUNT_TYPES:
            self.is_ai_agent = True
        elif self.is_ai_agent and self.account_type in (
            self.AccountType.HUMAN,
            self.AccountType.UNKNOWN,
        ):
            self.account_type = self.AccountType.DECLARED_AGENT
        else:
            self.is_ai_agent = False
        super().save(*args, **kwargs)

    @property
    def is_agent_account(self):
        """True for declared/organization AI agents (replaces raw is_ai_agent checks)."""
        return self.account_type in self.AGENT_ACCOUNT_TYPES

    def __str__(self):
        return self.public_name

    @property
    def public_name(self):
        if self.display_name:
            return self.display_name
        if self.identity_mode == self.IdentityMode.ANONYMOUS:
            return _("Anonymous")
        return self.username

    @property
    def show_username_publicly(self):
        return self.identity_mode != self.IdentityMode.ANONYMOUS

    @property
    def is_email_verified(self):
        return self.email_verified_at is not None

    @property
    def identity_mode_badge_class(self):
        return {
            self.IdentityMode.PUBLIC: "badge-identity-public",
            self.IdentityMode.PSEUDONYM: "badge-identity-pseudonym",
            self.IdentityMode.ANONYMOUS: "badge-identity-anonymous",
        }.get(self.identity_mode, "badge-identity-public")


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    popularity_points = models.IntegerField(default=0)
    reputation_points = models.IntegerField(default=0)
    prediction_count = models.PositiveIntegerField(default=0)
    correct_prediction_count = models.PositiveIntegerField(default=0)
    incorrect_prediction_count = models.PositiveIntegerField(default=0)
    neutral_prediction_count = models.PositiveIntegerField(default=0)
    scored_forecast_count = models.PositiveIntegerField(
        default=0,
        help_text="Forecasts that received reputation scoring (resolved or exited).",
    )
    reputation_score = models.FloatField(
        default=0.0,
        help_text="Average reputation P&L per scored forecast (ranking metric).",
    )
    popularity_score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-reputation_score"]
        indexes = [
            models.Index(fields=["-reputation_score"]),
            models.Index(fields=["-popularity_score"]),
        ]

    def __str__(self):
        return f"Profile: {self.user.username}"


class UserCategoryStats(models.Model):
    """Per-category reputation and popularity aggregates for a user."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="category_stats",
    )
    category_slug = models.CharField(max_length=50)
    reputation_points = models.IntegerField(default=0)
    popularity_points = models.IntegerField(default=0)
    prediction_count = models.PositiveIntegerField(default=0)
    correct_prediction_count = models.PositiveIntegerField(default=0)
    incorrect_prediction_count = models.PositiveIntegerField(default=0)
    scored_forecast_count = models.PositiveIntegerField(default=0)
    reputation_score = models.FloatField(default=0.0)
    popularity_score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "category_slug")]
        indexes = [
            models.Index(fields=["category_slug", "-reputation_score"]),
            models.Index(fields=["category_slug", "-popularity_score"]),
        ]
        ordering = ["category_slug"]
        verbose_name_plural = "User category stats"

    def __str__(self):
        return f"{self.user.username} · {self.category_slug}"


class AIAgentProfile(models.Model):
    """Operational trust/permission record for an AI (or hybrid) account.

    Account *classification* lives on ``User.account_type`` (§15); this profile
    holds the agent-specific trust level, granted scopes, and rate-limit tier
    that gate participation and MCP access (§17). New agents start read-only and
    earn write permissions progressively.
    """

    class OperatorType(models.TextChoices):
        INDIVIDUAL = "individual", _lazy("Individual")
        COMPANY = "company", _lazy("Company")
        RESEARCH = "research", _lazy("Research")
        UNKNOWN = "unknown", _lazy("Unknown")

    class AutonomyLevel(models.TextChoices):
        ASSISTANT_ONLY = "assistant_only", _lazy("Assistant only")
        HUMAN_SUPERVISED = "human_supervised", _lazy("Human supervised")
        SEMI_AUTONOMOUS = "semi_autonomous", _lazy("Semi-autonomous")
        AUTONOMOUS = "autonomous", _lazy("Autonomous")

    class TrustLevel(models.TextChoices):
        NEW = "new", _lazy("New")
        LIMITED = "limited", _lazy("Limited")
        STANDARD = "standard", _lazy("Standard")
        TRUSTED = "trusted", _lazy("Trusted")
        RESTRICTED = "restricted", _lazy("Restricted")
        BANNED = "banned", _lazy("Banned")

    class RateLimitTier(models.TextChoices):
        NEW = "new", _lazy("New")
        STANDARD = "standard", _lazy("Standard")
        TRUSTED = "trusted", _lazy("Trusted")
        THROTTLED = "throttled", _lazy("Throttled")

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="agent_profile",
    )
    agent_name = models.CharField(max_length=150)
    agent_operator = models.CharField(
        max_length=200,
        blank=True,
        help_text="Accountable human or organization operating this agent.",
    )
    operator_type = models.CharField(
        max_length=20,
        choices=OperatorType.choices,
        default=OperatorType.UNKNOWN,
    )
    model_provider = models.CharField(max_length=100, blank=True)
    model_name = models.CharField(max_length=100, blank=True)
    autonomy_level = models.CharField(
        max_length=20,
        choices=AutonomyLevel.choices,
        default=AutonomyLevel.HUMAN_SUPERVISED,
    )
    system_description = models.TextField(blank=True)
    public_description = models.TextField(
        blank=True,
        help_text="Public disclosure shown on the agent's profile.",
    )
    homepage_url = models.URLField(blank=True)
    is_verified_agent = models.BooleanField(default=False)
    trust_level = models.CharField(
        max_length=20,
        choices=TrustLevel.choices,
        default=TrustLevel.NEW,
        db_index=True,
    )
    allowed_scopes = models.JSONField(
        default=list,
        blank=True,
        help_text="Granted MCP/API scopes, e.g. ['markets:read', 'predictions:write'].",
    )
    rate_limit_tier = models.CharField(
        max_length=20,
        choices=RateLimitTier.choices,
        default=RateLimitTier.NEW,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "AI agent profile"

    def __str__(self):
        return self.agent_name

    @property
    def can_write(self):
        """Whether the agent's trust level permits any write action."""
        return self.trust_level in (
            self.TrustLevel.STANDARD,
            self.TrustLevel.TRUSTED,
        )


class AbuseEvent(models.Model):
    """Immutable record of an anti-abuse detection or moderation action (§16).

    Append-only audit trail surfaced in Django Admin. Stores only internal
    signals — never raw private identifiers in a way that leaks to public UI.
    """

    class EventType(models.TextChoices):
        RATE_LIMITED = "rate_limited", _lazy("Rate limited")
        DUPLICATE_CONTENT = "duplicate_content", _lazy("Duplicate content")
        SPAM_SUSPECTED = "spam_suspected", _lazy("Spam suspected")
        VELOCITY = "velocity", _lazy("Abnormal velocity")
        VOTE_MANIPULATION = "vote_manipulation", _lazy("Vote manipulation")
        REGISTRATION_RISK = "registration_risk", _lazy("Registration risk")
        MCP_ABUSE = "mcp_abuse", _lazy("MCP abuse")
        CIRCUIT_BREAKER = "circuit_breaker", _lazy("Circuit breaker tripped")
        MODERATION_ACTION = "moderation_action", _lazy("Moderation action")

    class Severity(models.TextChoices):
        INFO = "info", _lazy("Info")
        LOW = "low", _lazy("Low")
        MEDIUM = "medium", _lazy("Medium")
        HIGH = "high", _lazy("High")

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="abuse_events",
    )
    event_type = models.CharField(
        max_length=30,
        choices=EventType.choices,
        db_index=True,
    )
    severity = models.CharField(
        max_length=10,
        choices=Severity.choices,
        default=Severity.LOW,
        db_index=True,
    )
    scope = models.CharField(
        max_length=80,
        blank=True,
        help_text="What was being protected, e.g. 'comments', 'mcp:submit_prediction'.",
    )
    risk_score = models.PositiveIntegerField(default=0)
    action_taken = models.CharField(
        max_length=80,
        blank=True,
        help_text="e.g. 'throttled', 'quarantined', 'blocked', 'flagged'.",
    )
    reason = models.TextField(blank=True)
    signals = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["event_type", "-created_at"]),
            models.Index(fields=["severity", "-created_at"]),
        ]

    def __str__(self):
        who = self.user.username if self.user_id else "anonymous"
        return f"AbuseEvent({self.event_type}, {self.severity}) for {who}"


class Bookmark(models.Model):
    class TargetType(models.TextChoices):
        PREDICTION = "prediction", "Prediction"
        PULSE_POST = "pulse_post", "Pulse post"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookmarks",
    )
    target_type = models.CharField(max_length=20, choices=TargetType.choices)
    target_id = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "target_type", "target_id")]
        indexes = [
            models.Index(fields=["user", "target_type"]),
            models.Index(fields=["target_type", "target_id"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} bookmarked {self.target_type}:{self.target_id}"


class UserFollow(models.Model):
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="following_relations",
    )
    following = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="follower_relations",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("follower", "following")]
        indexes = [
            models.Index(fields=["follower"]),
            models.Index(fields=["following"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.follower.username} follows {self.following.username}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.follower_id and self.following_id and self.follower_id == self.following_id:
            raise ValidationError(_("Users cannot follow themselves."))


class TopicFollow(models.Model):
    """A user following a canonical market category (topic).

    Powers For You personalization and topic-scoped discovery. Slugs come from
    ``markets.categories.CANONICAL_CATEGORIES`` — never raw Polymarket tags.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="topic_follows",
    )
    category_slug = models.SlugField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "category_slug")]
        indexes = [models.Index(fields=["user"])]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} follows topic {self.category_slug}"


class MarketWatch(models.Model):
    """A user watching a specific market (resolution reminders + feed boost)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="market_watches",
    )
    market = models.ForeignKey(
        "markets.Market",
        on_delete=models.CASCADE,
        related_name="watchers",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "market")]
        indexes = [models.Index(fields=["user"]), models.Index(fields=["market"])]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} watches {self.market.slug}"


class ActivityStreak(models.Model):
    """Consecutive-day engagement streak for a user.

    A streak counts calendar days on which the user takes at least one
    engagement action (forecast, comment, vote, forum post). Streaks feed the
    POPULARITY dimension only — predictive reputation still comes solely from
    resolved predictions (AGENTS.md §6). Loss-aversion around an active streak
    is the core daily-habit retention loop.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="activity_streak",
    )
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_active_date = models.DateField(null=True, blank=True)
    risk_notified_date = models.DateField(
        null=True,
        blank=True,
        help_text="Last date a 'streak at risk' reminder was sent (dedupe guard).",
    )
    streak_7_completions = models.PositiveIntegerField(
        default=0,
        help_text="Times the user reached a 7-day streak milestone (stackable Week Warrior).",
    )
    streak_30_completions = models.PositiveIntegerField(
        default=0,
        help_text="Times the user reached a 30-day streak milestone (stackable Unstoppable).",
    )
    freeze_tokens = models.PositiveSmallIntegerField(
        default=0,
        help_text="Streak freezes available; one is consumed automatically when exactly one day is missed.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["last_active_date"]),
        ]

    def __str__(self):
        return f"Streak for {self.user.username}: {self.current_streak}d"

    def _reference_today(self, today=None):
        from django.utils import timezone

        return today or timezone.localdate()

    def is_active_today(self, today=None):
        today = self._reference_today(today)
        return self.last_active_date == today

    def is_alive(self, today=None):
        """True while the streak can still be continued (acted today or yesterday)."""
        from datetime import timedelta

        today = self._reference_today(today)
        if self.last_active_date is None:
            return False
        return self.last_active_date >= today - timedelta(days=1)

    def is_at_risk(self, today=None):
        """Alive but not yet extended today — one day from breaking."""
        return self.is_alive(today) and not self.is_active_today(today)

    def display_streak(self, today=None):
        """Streak value to show in the UI (0 once it has lapsed)."""
        if not self.is_alive(today):
            return 0
        return self.current_streak


class UserAchievement(models.Model):
    """Immutable record that a user unlocked a catalog achievement.

    The catalog itself lives in code (``accounts.achievement_services``); this
    table stores *which* achievement a user earned and *when*. Stackable
    milestones (e.g. Week Warrior) may have multiple rows with the same code.
    Achievements are badges (popularity-flavored social proof) — they never
    alter predictive reputation (AGENTS.md §6). Records are append-only and
    never deleted.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="achievements",
    )
    code = models.CharField(max_length=50)
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "code"]),
        ]
        ordering = ["awarded_at"]

    def __str__(self):
        return f"{self.user.username} unlocked {self.code}"


class UserMission(models.Model):
    """Daily mission progress for a user.

    The mission catalog lives in code (``accounts.mission_services``); this
    table tracks per-day progress. Completing a mission awards a small, capped
    POPULARITY bonus and never touches predictive reputation (AGENTS.md §6).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="missions",
    )
    code = models.CharField(max_length=50)
    period_date = models.DateField()
    progress = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "code", "period_date")]
        indexes = [
            models.Index(fields=["user", "period_date"]),
        ]
        ordering = ["-period_date"]

    def __str__(self):
        return f"{self.user.username} mission {self.code} ({self.period_date})"


class PushSubscription(models.Model):
    """A browser Web Push subscription (PWA service worker endpoint).

    One user can have several (multiple devices/browsers). Dead endpoints are
    pruned when the push service returns 404/410. Stores only the opaque
    endpoint + public keys needed to encrypt a push — no message content.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
    )
    endpoint = models.URLField(max_length=600, unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Push for {self.user.username} ({self.endpoint[:40]}…)"

    def as_subscription_info(self):
        return {
            "endpoint": self.endpoint,
            "keys": {"p256dh": self.p256dh, "auth": self.auth},
        }


class NotificationPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    notify_followed_predictions = models.BooleanField(
        default=True,
        help_text="Receive alerts when someone you follow publishes a forecast.",
    )
    notify_new_follower = models.BooleanField(
        default=True,
        help_text="Receive alerts when someone follows you.",
    )
    notify_votes_received = models.BooleanField(
        default=True,
        help_text="Receive alerts when someone upvotes or downvotes your content.",
    )
    notify_prediction_resolved = models.BooleanField(
        default=True,
        help_text="Receive alerts when a market resolves and reputation points are applied.",
    )
    notify_challenge_updates = models.BooleanField(
        default=True,
        help_text="Receive alerts about challenge invitations, event resolutions, and results.",
    )
    notify_replies = models.BooleanField(
        default=True,
        help_text="Receive alerts when someone replies to your comment.",
    )
    notify_mentions = models.BooleanField(
        default=True,
        help_text="Receive alerts when someone @mentions you.",
    )
    notify_market_resolving = models.BooleanField(
        default=True,
        help_text="Receive a reminder when a market you forecast is about to close.",
    )
    notify_in_app = models.BooleanField(
        default=True,
        help_text="Show alerts in the notification center.",
    )
    notify_push = models.BooleanField(
        default=True,
        help_text="Send browser push notifications (requires granting permission).",
    )
    notify_email = models.BooleanField(
        default=False,
        help_text="Send email alerts (requires email configuration).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Notification preferences"

    def __str__(self):
        return f"Alert preferences for {self.user.username}"


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        FOLLOWED_USER_PREDICTION = (
            "followed_user_prediction",
            "Followed user prediction",
        )
        NEW_FOLLOWER = ("new_follower", "New follower")
        UPVOTE_RECEIVED = ("upvote_received", "Upvote received")
        DOWNVOTE_RECEIVED = ("downvote_received", "Downvote received")
        PREDICTION_RESOLVED = ("prediction_resolved", "Prediction resolved")
        CHALLENGE_INVITATION = ("challenge_invitation", "Challenge invitation")
        CHALLENGE_MARKET_RESOLVED = (
            "challenge_market_resolved",
            "Challenge event resolved",
        )
        CHALLENGE_COMPLETED = ("challenge_completed", "Challenge completed")
        CHALLENGE_ACCEPTED = ("challenge_accepted", "Challenge accepted")
        COMMENT_REPLY = ("comment_reply", "Reply to your comment")
        MENTION = ("mention", "You were mentioned")
        MARKET_RESOLVING = ("market_resolving", "Market resolving soon")

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="triggered_notifications",
    )
    notification_type = models.CharField(
        max_length=40,
        choices=NotificationType.choices,
    )
    prediction = models.ForeignKey(
        "predictions.Prediction",
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    comment = models.ForeignKey(
        "comments.Comment",
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    pulse_post = models.ForeignKey(
        "pulse.Post",
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    pulse_comment = models.ForeignKey(
        "pulse.Comment",
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    user_follow = models.ForeignKey(
        UserFollow,
        on_delete=models.SET_NULL,
        related_name="notifications",
        null=True,
        blank=True,
    )
    vote_target_type = models.CharField(max_length=20, blank=True)
    vote_target_id = models.PositiveIntegerField(null=True, blank=True)
    reputation_event = models.ForeignKey(
        "reputation.ReputationEvent",
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    challenge = models.ForeignKey(
        "challenges.Challenge",
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    market = models.ForeignKey(
        "markets.Market",
        on_delete=models.CASCADE,
        related_name="challenge_notifications",
        null=True,
        blank=True,
    )
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "-created_at"]),
            models.Index(fields=["recipient", "read_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["recipient", "notification_type", "prediction"],
                condition=models.Q(prediction__isnull=False),
                name="unique_prediction_notification",
            ),
            models.UniqueConstraint(
                fields=["user_follow"],
                condition=models.Q(user_follow__isnull=False),
                name="unique_follow_notification",
            ),
            models.UniqueConstraint(
                fields=["recipient", "notification_type", "challenge", "market"],
                condition=models.Q(
                    challenge__isnull=False,
                    market__isnull=False,
                    notification_type="challenge_market_resolved",
                ),
                name="unique_challenge_market_notification",
            ),
            models.UniqueConstraint(
                fields=["recipient", "notification_type", "challenge"],
                condition=models.Q(
                    challenge__isnull=False,
                    notification_type="challenge_completed",
                ),
                name="unique_challenge_completed_notification",
            ),
            models.UniqueConstraint(
                fields=["recipient", "notification_type", "challenge"],
                condition=models.Q(
                    challenge__isnull=False,
                    notification_type="challenge_invitation",
                ),
                name="unique_challenge_invitation_notification",
            ),
            models.UniqueConstraint(
                fields=["recipient", "notification_type", "challenge", "actor"],
                condition=models.Q(
                    challenge__isnull=False,
                    notification_type="challenge_accepted",
                ),
                name="unique_challenge_accepted_notification",
            ),
            models.UniqueConstraint(
                fields=["recipient", "notification_type", "market"],
                condition=models.Q(
                    market__isnull=False,
                    notification_type="market_resolving",
                ),
                name="unique_market_resolving_notification",
            ),
        ]

    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.notification_type}"

    @property
    def is_read(self):
        return self.read_at is not None

    @property
    def action_url(self):
        from django.urls import reverse

        if self.notification_type == self.NotificationType.NEW_FOLLOWER:
            return reverse("accounts:profile", kwargs={"username": self.actor.username})
        if self.notification_type == self.NotificationType.FOLLOWED_USER_PREDICTION:
            if self.prediction_id:
                return reverse(
                    "markets:detail",
                    kwargs={"slug": self.prediction.market.slug},
                )
        if self.notification_type in (
            self.NotificationType.UPVOTE_RECEIVED,
            self.NotificationType.DOWNVOTE_RECEIVED,
        ):
            if self.comment_id:
                return reverse(
                    "markets:detail",
                    kwargs={"slug": self.comment.market.slug},
                )
            if self.prediction_id:
                return reverse(
                    "markets:detail",
                    kwargs={"slug": self.prediction.market.slug},
                )
        if self.notification_type == self.NotificationType.PREDICTION_RESOLVED:
            if self.prediction_id:
                return reverse(
                    "markets:detail",
                    kwargs={"slug": self.prediction.market.slug},
                )
        if self.challenge_id and self.notification_type in (
            self.NotificationType.CHALLENGE_INVITATION,
            self.NotificationType.CHALLENGE_MARKET_RESOLVED,
            self.NotificationType.CHALLENGE_COMPLETED,
            self.NotificationType.CHALLENGE_ACCEPTED,
        ):
            return reverse("challenges:detail", kwargs={"pk": self.challenge_id})
        if self.notification_type in (
            self.NotificationType.COMMENT_REPLY,
            self.NotificationType.MENTION,
        ):
            if self.comment_id:
                return reverse("markets:detail", kwargs={"slug": self.comment.market.slug})
            if self.pulse_comment_id:
                return reverse("forum:detail", kwargs={"post_id": self.pulse_comment.post_id})
            if self.pulse_post_id:
                return reverse("forum:detail", kwargs={"post_id": self.pulse_post_id})
        if self.notification_type == self.NotificationType.MARKET_RESOLVING:
            if self.market_id:
                return reverse("markets:detail", kwargs={"slug": self.market.slug})
        return reverse("accounts:notifications")

    @property
    def action_label(self):
        if self.notification_type == self.NotificationType.NEW_FOLLOWER:
            return "View profile"
        if self.notification_type == self.NotificationType.FOLLOWED_USER_PREDICTION:
            return "View market"
        if self.notification_type in (
            self.NotificationType.UPVOTE_RECEIVED,
            self.NotificationType.DOWNVOTE_RECEIVED,
        ):
            return "View content"
        if self.notification_type == self.NotificationType.PREDICTION_RESOLVED:
            return "View market"
        if self.notification_type in (
            self.NotificationType.CHALLENGE_INVITATION,
            self.NotificationType.CHALLENGE_MARKET_RESOLVED,
            self.NotificationType.CHALLENGE_COMPLETED,
            self.NotificationType.CHALLENGE_ACCEPTED,
        ):
            return "View challenge"
        if self.notification_type in (
            self.NotificationType.COMMENT_REPLY,
            self.NotificationType.MENTION,
        ):
            return "View conversation"
        if self.notification_type == self.NotificationType.MARKET_RESOLVING:
            return "View market"
        return "View"


class EmailVerificationToken(models.Model):
    """One-time token to confirm a user's email address."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_verification_tokens",
    )
    token = models.CharField(max_length=64, unique=True, db_index=True)
    email = models.EmailField(
        help_text="Email address snapshot at the time the token was issued.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"Email verification for {self.user_id} ({self.email})"

    @property
    def is_expired(self):
        from django.utils import timezone

        return timezone.now() >= self.expires_at

    @property
    def is_usable(self):
        return self.used_at is None and not self.is_expired


class SubscriberAudience(models.TextChoices):
    """Who can view a piece of creator content (no payment flow — access is membership)."""

    PUBLIC = "public", _lazy("Public")
    SUBSCRIBERS = "subscribers", _lazy("Subscribers only")


class CreatorProgram(models.Model):
    """Creator monetization settings for a user (subscriptions without on-platform payments)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="creator_program",
    )
    is_enabled = models.BooleanField(
        default=False,
        help_text="When enabled, the user can publish subscriber-only content and accept members.",
    )
    tagline = models.CharField(max_length=300, blank=True)
    welcome_message = models.TextField(blank=True)
    monthly_price_cents = models.PositiveIntegerField(
        default=500,
        help_text="Displayed monthly price in cents (no payment processing in MVP).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Creator program for {self.user.username}"

    @property
    def monthly_price_display(self):
        dollars = self.monthly_price_cents / 100
        if dollars == int(dollars):
            return str(int(dollars))
        return f"{dollars:.2f}"


class CreatorSubscription(models.Model):
    """Membership linking a subscriber to a creator (no wallet or payment state)."""

    class Status(models.TextChoices):
        ACTIVE = "active", _lazy("Active")
        CANCELLED = "cancelled", _lazy("Cancelled")

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="creator_subscriptions",
    )
    subscriber = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="creator_memberships",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["creator", "status", "-started_at"]),
            models.Index(fields=["subscriber", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["creator", "subscriber"],
                name="accounts_unique_creator_subscriber_pair",
            ),
        ]

    def __str__(self):
        return f"{self.subscriber.username} → {self.creator.username} ({self.status})"
