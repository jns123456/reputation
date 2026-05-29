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

    display_name = models.CharField(max_length=150, blank=True)
    identity_mode = models.CharField(
        max_length=20,
        choices=IdentityMode.choices,
        default=IdentityMode.PUBLIC,
        help_text="How the user appears publicly on the platform.",
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
    avatar = models.ImageField(upload_to="avatars/%Y/%m/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["username"]

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
    reputation_score = models.FloatField(default=0.0)
    popularity_score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-reputation_score"]

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
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="agent_profile",
    )
    agent_name = models.CharField(max_length=150)
    model_provider = models.CharField(max_length=100, blank=True)
    model_name = models.CharField(max_length=100, blank=True)
    system_description = models.TextField(blank=True)
    is_verified_agent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "AI agent profile"

    def __str__(self):
        return self.agent_name


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
    table only stores *which* achievement a user earned and *when*. Achievements
    are badges (popularity-flavored social proof) — they never alter predictive
    reputation (AGENTS.md §6). Records are append-only and never deleted.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="achievements",
    )
    code = models.CharField(max_length=50)
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "code")]
        indexes = [
            models.Index(fields=["user", "code"]),
        ]
        ordering = ["awarded_at"]

    def __str__(self):
        return f"{self.user.username} unlocked {self.code}"


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
