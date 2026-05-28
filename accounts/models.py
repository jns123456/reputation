from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class IdentityMode(models.TextChoices):
        PUBLIC = "public", "Public"
        PSEUDONYM = "pseudonym", "Pseudonym"
        ANONYMOUS = "anonymous", "Anonymous"

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
    is_ai_agent = models.BooleanField(default=False)
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
            return "Anonymous"
        return self.username

    @property
    def show_username_publicly(self):
        return self.identity_mode != self.IdentityMode.ANONYMOUS

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
            raise ValidationError("Users cannot follow themselves.")


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
    notify_in_app = models.BooleanField(
        default=True,
        help_text="Show alerts in the notification center.",
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
        return "View"
