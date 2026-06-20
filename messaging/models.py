"""Private 1:1 direct messages between users."""

from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Conversation(models.Model):
    """Canonical pair of users in ascending PK order."""

    user_one = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dm_conversations_as_one",
    )
    user_two = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dm_conversations_as_two",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(user_one_id__lt=F("user_two_id")),
                name="dm_user_order",
            ),
            models.UniqueConstraint(
                fields=["user_one", "user_two"],
                name="dm_unique_pair",
            ),
        ]

    def __str__(self):
        return f"DM {self.user_one.username} ↔ {self.user_two.username}"

    def other_user(self, user):
        if user.id == self.user_one_id:
            return self.user_two
        if user.id == self.user_two_id:
            return self.user_one
        raise ValueError("User is not a participant in this conversation.")

    def involves_user(self, user):
        return user.id in {self.user_one_id, self.user_two_id}


class ConversationParticipant(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="participant_states",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dm_participant_states",
    )
    last_read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "user"],
                name="dm_unique_participant",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} in conversation {self.conversation_id}"


class Message(models.Model):
    MAX_BODY_LENGTH = 2000

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_dm_messages",
    )
    body = models.TextField(max_length=MAX_BODY_LENGTH)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
        ]

    def __str__(self):
        preview = self.body[:40] + ("…" if len(self.body) > 40 else "")
        return f"Message from {self.sender.username}: {preview}"
