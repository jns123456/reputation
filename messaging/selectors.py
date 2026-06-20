"""Direct message read queries."""

from django.db.models import Prefetch, Q

from messaging.models import Conversation, ConversationParticipant, Message


def get_user_conversation(*, user, conversation_id):
    return (
        Conversation.objects.filter(
            Q(user_one=user) | Q(user_two=user),
            pk=conversation_id,
        )
        .select_related("user_one", "user_two", "user_one__profile", "user_two__profile")
        .first()
    )


def get_inbox_conversations(*, user, limit=50):
    latest_message = Prefetch(
        "messages",
        queryset=Message.objects.select_related("sender").order_by("-created_at")[:1],
        to_attr="latest_messages",
    )
    participant_state = Prefetch(
        "participant_states",
        queryset=ConversationParticipant.objects.filter(user=user),
        to_attr="viewer_states",
    )
    return (
        Conversation.objects.filter(Q(user_one=user) | Q(user_two=user))
        .select_related("user_one", "user_two", "user_one__profile", "user_two__profile")
        .prefetch_related(latest_message, participant_state)
        .order_by("-updated_at")[:limit]
    )


def get_conversation_messages(*, conversation, limit=100, before_id=None):
    qs = (
        Message.objects.filter(conversation=conversation)
        .select_related("sender", "sender__profile")
        .order_by("created_at")
    )
    if before_id:
        qs = qs.filter(pk__lt=before_id)
    messages = list(qs[:limit])
    if before_id:
        return messages
    if len(messages) > limit:
        return messages[-limit:]
    return messages


def get_unread_message_count(*, user):
    total = 0
    states = ConversationParticipant.objects.filter(user=user).select_related("conversation")
    for state in states:
        since = state.last_read_at or state.conversation.created_at
        total += (
            state.conversation.messages.filter(created_at__gt=since)
            .exclude(sender=user)
            .count()
        )
    return total


def conversation_unread_count(*, conversation, user):
    state = ConversationParticipant.objects.filter(
        conversation=conversation,
        user=user,
    ).first()
    since = (state.last_read_at if state else None) or conversation.created_at
    return conversation.messages.filter(created_at__gt=since).exclude(sender=user).count()


def get_viewer_read_state(*, conversation, user):
    return ConversationParticipant.objects.filter(conversation=conversation, user=user).first()
