"""Tests for @mention parsing and reply/mention notifications."""

from unittest.mock import patch

from django.template import Context, Template
from django.test import TestCase
from django.urls import reverse

from accounts.mention_services import extract_mention_usernames
from accounts.models import Notification
from accounts.notification_services import notify_mentions
from comments.services import create_comment
from conftest import create_market, create_user
from predictions.models import Prediction
from pulse.services import create_post, create_pulse_comment


class ExtractMentionsTests(TestCase):
    def test_basic_mentions(self):
        self.assertEqual(
            extract_mention_usernames("hey @alice and @bob_99"),
            ["alice", "bob_99"],
        )

    def test_dedupes_and_preserves_order(self):
        self.assertEqual(
            extract_mention_usernames("@alice @bob @alice"),
            ["alice", "bob"],
        )

    def test_ignores_email_like_text(self):
        self.assertEqual(extract_mention_usernames("write to bob@example.com"), [])

    def test_empty_body(self):
        self.assertEqual(extract_mention_usernames(""), [])

    def test_caps_number_of_mentions(self):
        body = " ".join(f"@user{i}" for i in range(20))
        self.assertEqual(len(extract_mention_usernames(body)), 10)


class NotifyMentionsTests(TestCase):
    def setUp(self):
        self.actor = create_user("author")
        self.alice = create_user("alice")
        self.bob = create_user("bob")

    def test_creates_mention_notifications(self):
        created = notify_mentions(actor=self.actor, body="hi @alice and @bob")
        self.assertEqual(len(created), 2)
        self.assertEqual(
            Notification.objects.filter(
                notification_type=Notification.NotificationType.MENTION
            ).count(),
            2,
        )

    def test_excludes_actor_self_mention(self):
        created = notify_mentions(actor=self.actor, body="talking to myself @author")
        self.assertEqual(created, [])

    def test_respects_mention_preference(self):
        self.alice.notification_preferences.notify_mentions = False
        self.alice.notification_preferences.save()
        created = notify_mentions(actor=self.actor, body="@alice @bob")
        recipients = {n.recipient_id for n in created}
        self.assertNotIn(self.alice.id, recipients)
        self.assertIn(self.bob.id, recipients)

    def test_exclude_user_ids(self):
        created = notify_mentions(
            actor=self.actor, body="@alice @bob", exclude_user_ids={self.alice.id}
        )
        recipients = {n.recipient_id for n in created}
        self.assertEqual(recipients, {self.bob.id})


class CommentReplyAndMentionTests(TestCase):
    def setUp(self):
        self._refresh = patch(
            "predictions.services._refresh_market_odds", side_effect=lambda m: m
        )
        self._refresh.start()
        self.addCleanup(self._refresh.stop)

        self.predictor = create_user("predictor")
        self.commenter = create_user("commenter")
        self.replier = create_user("replier")
        self.mentioned = create_user("mentioned")
        self.market = create_market()
        from predictions.services import create_prediction

        self.prediction = create_prediction(
            user=self.predictor, market=self.market, predicted_outcome="Yes"
        )
        self.top_comment = create_comment(
            user=self.commenter,
            market=self.market,
            body="Top-level take",
            prediction=self.prediction,
        )

    def test_reply_notifies_parent_author(self):
        create_comment(
            user=self.replier,
            market=self.market,
            body="I disagree",
            parent_comment=self.top_comment,
            prediction=self.prediction,
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.commenter,
                actor=self.replier,
                notification_type=Notification.NotificationType.COMMENT_REPLY,
            ).exists()
        )

    def test_mention_in_comment_notifies_user(self):
        create_comment(
            user=self.replier,
            market=self.market,
            body="hey @mentioned look at this",
            parent_comment=self.top_comment,
            prediction=self.prediction,
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.mentioned,
                notification_type=Notification.NotificationType.MENTION,
                comment__isnull=False,
            ).exists()
        )

    def test_reply_recipient_not_double_notified_as_mention(self):
        # Replier mentions the parent author too -> only the reply notification.
        create_comment(
            user=self.replier,
            market=self.market,
            body="@commenter good point",
            parent_comment=self.top_comment,
            prediction=self.prediction,
        )
        mention_count = Notification.objects.filter(
            recipient=self.commenter,
            notification_type=Notification.NotificationType.MENTION,
        ).count()
        self.assertEqual(mention_count, 0)


class ForumMentionTests(TestCase):
    def setUp(self):
        self.author = create_user("forum_author")
        self.commenter = create_user("forum_commenter")
        self.mentioned = create_user("forum_mentioned")

    def test_post_mention_notifies(self):
        create_post(user=self.author, body="big news for @forum_mentioned")
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.mentioned,
                notification_type=Notification.NotificationType.MENTION,
                pulse_post__isnull=False,
            ).exists()
        )

    def test_forum_reply_notifies_parent(self):
        post = create_post(user=self.author, body="discuss")
        parent = create_pulse_comment(user=self.commenter, post=post, body="first")
        create_pulse_comment(
            user=self.mentioned, post=post, body="reply", parent_comment=parent
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.commenter,
                actor=self.mentioned,
                notification_type=Notification.NotificationType.COMMENT_REPLY,
                pulse_comment__isnull=False,
            ).exists()
        )


class MentionSuggestionSelectorTests(TestCase):
    def setUp(self):
        self.me = create_user("me")
        self.alice = create_user("alice")
        self.bob = create_user("bob")
        self.charlie = create_user("charlie")
        from accounts.follow_services import toggle_follow

        toggle_follow(follower=self.me, following_user=self.alice)
        toggle_follow(follower=self.me, following_user=self.bob)

    def test_returns_followed_users_only(self):
        from accounts.mention_selectors import search_following_for_mention

        usernames = list(
            search_following_for_mention(user=self.me).values_list("username", flat=True)
        )
        self.assertEqual(set(usernames), {"alice", "bob"})

    def test_filters_by_prefix(self):
        from accounts.mention_selectors import search_following_for_mention

        usernames = list(
            search_following_for_mention(user=self.me, prefix="al").values_list(
                "username", flat=True
            )
        )
        self.assertEqual(usernames, ["alice"])


class MentionSuggestionsViewTests(TestCase):
    def setUp(self):
        from django.test import Client

        self.client = Client()
        self.me = create_user("me")
        self.alice = create_user("alice")
        self.bob = create_user("bob")
        create_user("stranger")
        from accounts.follow_services import toggle_follow

        toggle_follow(follower=self.me, following_user=self.alice)
        toggle_follow(follower=self.me, following_user=self.bob)
        self.url = reverse("accounts:mention_suggestions_partial")

    def test_requires_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_returns_followed_users_matching_prefix(self):
        self.client.force_login(self.me)
        response = self.client.get(self.url, {"q": "al"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "alice")
        self.assertNotContains(response, "bob")
        self.assertNotContains(response, "stranger")

    def test_empty_query_lists_recent_follows(self):
        self.client.force_login(self.me)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "alice")
        self.assertContains(response, "bob")


class MentionNotificationDisplayTests(TestCase):
    def setUp(self):
        self.actor = create_user("notifier")
        self.recipient = create_user("mentioned_user")

    def _render_message(self, notification):
        template = Template(
            "{% load notification_tags %}{% notification_message notification %}"
        )
        return template.render(Context({"notification": notification})).strip()

    def test_mention_notification_message_includes_actor(self):
        notification = notify_mentions(
            actor=self.actor,
            body="@mentioned_user hello",
        )[0]
        message = self._render_message(notification)
        self.assertIn(self.actor.public_name, message)
        self.assertIn("mentioned you", message)

    def test_comment_reply_notification_message(self):
        from accounts.notification_services import notify_comment_reply
        from comments.models import Comment

        comment = Comment.objects.create(
            user=self.recipient,
            market=create_market(),
            body="parent",
        )
        reply = Comment.objects.create(
            user=self.actor,
            market=comment.market,
            body="child",
            parent_comment=comment,
        )
        notification = notify_comment_reply(comment=reply)
        message = self._render_message(notification)
        self.assertIn(self.actor.public_name, message)
        self.assertIn("replied to your comment", message)

    def test_mention_action_url_deep_links_market_comment(self):
        from comments.models import Comment

        market = create_market()
        comment = Comment.objects.create(
            user=self.actor,
            market=market,
            body="@mentioned_user check this",
        )
        notify_mentions(actor=self.actor, body=comment.body, comment=comment)
        notification = Notification.objects.get(
            recipient=self.recipient,
            notification_type=Notification.NotificationType.MENTION,
        )
        self.assertIn(f"#market-comment-{comment.id}", notification.action_url)
