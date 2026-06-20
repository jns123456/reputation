"""Direct message business logic."""

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from messaging.models import Conversation, ConversationParticipant, Message


def canonical_user_pair(user_a, user_b):
    if user_a.id == user_b.id:
        raise ValueError(_("You cannot message yourself."))
    if user_a.id < user_b.id:
        return user_a, user_b
    return user_b, user_a


def get_or_create_conversation(*, user_a, user_b):
    one, two = canonical_user_pair(user_a, user_b)
    with transaction.atomic():
        conversation, created = Conversation.objects.get_or_create(
            user_one=one,
            user_two=two,
        )
        if created:
            ConversationParticipant.objects.bulk_create(
                [
                    ConversationParticipant(conversation=conversation, user=one),
                    ConversationParticipant(conversation=conversation, user=two),
                ]
            )
    return conversation


def send_message(*, sender, recipient, body):
    from accounts.write_guard import guard_write_action

    body = (body or "").strip()
    if not body:
        raise ValueError(_("Message cannot be empty."))
    if len(body) > Message.MAX_BODY_LENGTH:
        raise ValueError(
            _("Message is too long (max %(max)s characters).")
            % {"max": Message.MAX_BODY_LENGTH}
        )

    guard_write_action(
        action="message",
        user=sender,
        text=body,
        content_scope="write:message",
    )

    conversation = get_or_create_conversation(user_a=sender, user_b=recipient)
    with transaction.atomic():
        message = Message.objects.create(
            conversation=conversation,
            sender=sender,
            body=body,
        )
        Conversation.objects.filter(pk=conversation.pk).update(updated_at=timezone.now())
        ConversationParticipant.objects.filter(
            conversation=conversation,
            user=sender,
        ).update(last_read_at=timezone.now())

    from accounts.notification_services import notify_direct_message
    from messaging.nav_cache import invalidate_dm_nav_cache

    notify_direct_message(message=message, recipient=recipient)
    invalidate_dm_nav_cache(recipient.id)
    invalidate_dm_nav_cache(sender.id)
    return message


def mark_conversation_read(*, user, conversation):
    if not conversation.involves_user(user):
        raise ValueError(_("You are not part of this conversation."))
    ConversationParticipant.objects.filter(
        conversation=conversation,
        user=user,
    ).update(last_read_at=timezone.now())
    from messaging.nav_cache import invalidate_dm_nav_cache

    invalidate_dm_nav_cache(user.id)
