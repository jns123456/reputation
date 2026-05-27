from django.conf import settings
from django.core.validators import MaxLengthValidator
from django.db import models
from django.utils import timezone


class Post(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pulse_posts",
    )
    body = models.CharField(
        max_length=200,
        blank=True,
        validators=[MaxLengthValidator(200)],
    )
    image = models.ImageField(upload_to="pulse/posts/%Y/%m/%d/", blank=True)
    reposted_from = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="reposts",
    )
    popularity_score = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-popularity_score", "-created_at"]),
            models.Index(fields=["reposted_from"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "reposted_from"],
                condition=models.Q(reposted_from__isnull=False),
                name="pulse_unique_repost_per_user",
            ),
        ]

    @property
    def is_repost(self):
        return self.reposted_from_id is not None

    @property
    def original_post(self):
        post = self
        while post.reposted_from_id is not None:
            post = post.reposted_from
        return post

    def __str__(self):
        preview = self.body[:40] if self.body else "(image)"
        return f"Pulse by {self.user.username}: {preview}"


class Comment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pulse_comments",
    )
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    parent_comment = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="replies",
    )
    body = models.TextField()
    popularity_score = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-popularity_score", "-created_at"]
        indexes = [
            models.Index(fields=["post", "parent_comment"]),
        ]

    def __str__(self):
        return f"Pulse comment by {self.user.username} on post {self.post_id}"


class Poll(models.Model):
    post = models.OneToOneField(
        Post,
        on_delete=models.CASCADE,
        related_name="poll",
    )
    ends_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_closed(self):
        return timezone.now() >= self.ends_at

    def __str__(self):
        return f"Poll on post {self.post_id}"


class PollOption(models.Model):
    poll = models.ForeignKey(
        Poll,
        on_delete=models.CASCADE,
        related_name="options",
    )
    text = models.CharField(max_length=50)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["poll", "position"],
                name="pulse_unique_poll_option_position",
            ),
        ]

    def __str__(self):
        return self.text[:40]


class PollVote(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pulse_poll_votes",
    )
    poll = models.ForeignKey(
        Poll,
        on_delete=models.CASCADE,
        related_name="votes",
    )
    option = models.ForeignKey(
        PollOption,
        on_delete=models.CASCADE,
        related_name="votes",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "poll"],
                name="pulse_unique_poll_vote_per_user",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} voted on poll {self.poll_id}"
