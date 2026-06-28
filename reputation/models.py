from django.conf import settings
from django.db import models


class ReputationEvent(models.Model):
    class EventType(models.TextChoices):
        CORRECT_PREDICTION = "correct_prediction", "Correct prediction"
        INCORRECT_PREDICTION = "incorrect_prediction", "Incorrect prediction"
        EXITED_PREDICTION = "exited_prediction", "Exited prediction"
        VOID_PREDICTION = "void_prediction", "Void prediction"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reputation_events",
    )
    prediction = models.ForeignKey(
        "predictions.Prediction",
        on_delete=models.CASCADE,
        related_name="reputation_events",
    )
    event_type = models.CharField(max_length=50, choices=EventType.choices)
    points_delta = models.IntegerField()
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["prediction", "-created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["prediction", "event_type"],
                name="reputationevent_unique_prediction_event_type",
            ),
        ]

    def __str__(self):
        return f"{self.event_type}: {self.points_delta} for {self.user.username}"


class SeasonAward(models.Model):
    """Permanent badge for a top finish in a quarterly reputation season.

    Awards are append-only social proof derived from immutable
    ``ReputationEvent`` history — they never alter scoring. ``category_slug``
    is blank for the global season board.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="season_awards",
    )
    season = models.CharField(max_length=10)  # e.g. "2026-Q2"
    category_slug = models.SlugField(max_length=100, blank=True, default="")
    rank = models.PositiveSmallIntegerField()
    reputation_points = models.IntegerField(default=0)
    reputation_score = models.FloatField(default=0)
    scored_forecast_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "season", "category_slug")]
        indexes = [
            models.Index(fields=["season", "category_slug", "rank"]),
            models.Index(fields=["user", "-created_at"]),
        ]
        ordering = ["season", "category_slug", "rank"]

    def __str__(self):
        scope = self.category_slug or "global"
        return f"{self.user.username} #{self.rank} {scope} {self.season}"


class WeeklyContestWinner(models.Model):
    """Weekly contest winner — one row per prize category (absolute / relative).

    Derived from immutable ``ReputationEvent`` history during the ISO calendar
    week. Cash prizes are off-platform; ``prize_usd`` is display-only.
    """

    class PrizeType(models.TextChoices):
        ABSOLUTE = "absolute", "Absolute reputation points"
        RELATIVE = "relative", "Reputation per forecast"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="weekly_contest_wins",
    )
    week_code = models.CharField(max_length=10)  # e.g. "2026-06-21" (starting Sunday)
    prize_type = models.CharField(max_length=20, choices=PrizeType.choices)
    reputation_points = models.IntegerField(default=0)
    reputation_score = models.FloatField(default=0)
    scored_forecast_count = models.PositiveIntegerField(default=0)
    prize_usd = models.PositiveSmallIntegerField(default=5)
    notified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the winner email and login alert were sent.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["week_code", "prize_type"],
                name="weeklycontestwinner_unique_week_prize",
            ),
        ]
        indexes = [
            models.Index(fields=["week_code", "prize_type"]),
            models.Index(fields=["user", "-created_at"]),
        ]
        ordering = ["-week_code", "prize_type"]

    def __str__(self):
        return f"{self.user.username} {self.prize_type} {self.week_code}"


class ContestPayoutRequest(models.Model):
    """Off-platform USDT/USDC withdrawal request for weekly contest earnings.

    PredictStamp does not custody funds — admins mark requests paid manually.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        PAID = "paid", "Paid"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    class Chain(models.TextChoices):
        ETHEREUM = "ethereum", "Ethereum (ERC-20)"
        BASE = "base", "Base"
        POLYGON = "polygon", "Polygon"
        BSC = "bsc", "BNB Smart Chain (BEP-20)"
        ARBITRUM = "arbitrum", "Arbitrum"
        OPTIMISM = "optimism", "Optimism"
        TRON = "tron", "Tron (TRC-20)"
        SOLANA = "solana", "Solana"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="contest_payout_requests",
    )
    amount_usd = models.DecimalField(max_digits=8, decimal_places=2)
    usdc_address = models.CharField(max_length=128)
    chain = models.CharField(max_length=20, choices=Chain.choices, default=Chain.BASE)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    admin_note = models.TextField(blank=True)
    tx_hash = models.CharField(max_length=66, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} ${self.amount_usd} {self.status}"


class PopularityEvent(models.Model):
    class EventType(models.TextChoices):
        UPVOTE_RECEIVED = "upvote_received", "Upvote received"
        DOWNVOTE_RECEIVED = "downvote_received", "Downvote received"
        COMMENT_POSTED = "comment_posted", "Comment posted"
        REPLY_RECEIVED = "reply_received", "Reply received"
        POST_PUBLISHED = "post_published", "Post published"
        REPOST_RECEIVED = "repost_received", "Repost received"
        STREAK_MILESTONE = "streak_milestone", "Activity streak milestone"
        SHARE_RECEIVED = "share_received", "Share received"
        MISSION_COMPLETED = "mission_completed", "Mission completed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="popularity_events",
    )
    comment = models.ForeignKey(
        "comments.Comment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="popularity_events",
    )
    prediction = models.ForeignKey(
        "predictions.Prediction",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="popularity_events",
    )
    pulse_post = models.ForeignKey(
        "pulse.Post",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="popularity_events",
    )
    pulse_comment = models.ForeignKey(
        "pulse.Comment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="popularity_events",
    )
    event_type = models.CharField(max_length=50, choices=EventType.choices)
    points_delta = models.IntegerField()
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["prediction", "-created_at"]),
            models.Index(fields=["comment", "-created_at"]),
            models.Index(fields=["pulse_post", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.event_type}: {self.points_delta} for {self.user.username}"
