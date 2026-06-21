"""Tests for private direct messages."""

from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Notification
from conftest import create_user
from messaging.models import Conversation, Message
from messaging.selectors import get_unread_message_count
from messaging.services import get_or_create_conversation, send_message


class DirectMessageServiceTests(TestCase):
    def setUp(self):
        self.alice = create_user("alice")
        self.bob = create_user("bob")

    def test_get_or_create_conversation_is_idempotent(self):
        first = get_or_create_conversation(user_a=self.alice, user_b=self.bob)
        second = get_or_create_conversation(user_a=self.bob, user_b=self.alice)
        self.assertEqual(first.id, second.id)
        self.assertEqual(Conversation.objects.count(), 1)

    def test_send_message_creates_message_and_notifies_recipient(self):
        message = send_message(sender=self.alice, recipient=self.bob, body="Hey Bob")
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(message.body, "Hey Bob")
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.bob,
                actor=self.alice,
                notification_type=Notification.NotificationType.DIRECT_MESSAGE,
                dm_message=message,
            ).exists()
        )

    def test_unread_count_for_recipient(self):
        conversation = get_or_create_conversation(user_a=self.alice, user_b=self.bob)
        send_message(sender=self.alice, recipient=self.bob, body="Ping")
        self.assertEqual(get_unread_message_count(user=self.bob), 1)
        self.assertEqual(get_unread_message_count(user=self.alice), 0)

        from messaging.services import mark_conversation_read

        mark_conversation_read(user=self.bob, conversation=conversation)
        self.assertEqual(get_unread_message_count(user=self.bob), 0)

    def test_cannot_message_self(self):
        with self.assertRaises(ValueError):
            send_message(sender=self.alice, recipient=self.alice, body="solo")

    def test_same_body_can_be_sent_to_multiple_recipients(self):
        carol = create_user("carol")
        send_message(sender=self.alice, recipient=self.bob, body="Hola")
        send_message(sender=self.alice, recipient=carol, body="Hola")
        self.assertEqual(Message.objects.count(), 2)

    def test_same_body_can_be_resent_in_one_conversation(self):
        send_message(sender=self.alice, recipient=self.bob, body="Hola")
        send_message(sender=self.alice, recipient=self.bob, body="Hola")
        self.assertEqual(Message.objects.count(), 2)


class DirectMessageViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.alice = create_user("alice")
        self.bob = create_user("bob")
        self.client.force_login(self.alice)

    def test_start_conversation_from_profile(self):
        response = self.client.get(reverse("messages:start", kwargs={"username": "bob"}))
        self.assertEqual(response.status_code, 302)
        conversation = Conversation.objects.get()
        self.assertEqual(response.url, reverse("messages:thread", kwargs={"conversation_id": conversation.id}))

    def test_inbox_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("messages:inbox"))
        self.assertEqual(response.status_code, 302)

    def test_send_message_via_post(self):
        conversation = get_or_create_conversation(user_a=self.alice, user_b=self.bob)
        response = self.client.post(
            reverse("messages:send", kwargs={"conversation_id": conversation.id}),
            {"body": "Hello there"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(conversation.messages.count(), 1)
