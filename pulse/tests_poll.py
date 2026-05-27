"""Unit tests for forum poll logic."""

from django.test import TestCase

from accounts.models import User
from pulse.models import Poll
from pulse.poll_forms import parse_poll_options_from_post, validate_poll_payload
from pulse.selectors import build_poll_context
from pulse.services import create_post, vote_on_poll


class PollServiceTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username="author", password="pass")
        self.voter = User.objects.create_user(username="voter", password="pass")

    def test_create_post_with_poll(self):
        post = create_post(
            user=self.author,
            body="Who wins?",
            poll_payload={"options": ["Team A", "Team B"], "duration_days": 3},
        )
        poll = Poll.objects.get(post=post)
        self.assertEqual(poll.options.count(), 2)
        self.assertFalse(poll.is_closed)

    def test_vote_on_poll_and_results(self):
        post = create_post(
            user=self.author,
            body="Pick one",
            poll_payload={"options": ["Red", "Blue"], "duration_days": 1},
        )
        poll = Poll.objects.get(post=post)
        option = poll.options.get(text="Red")
        vote_on_poll(user=self.voter, poll=poll, option=option)
        context = build_poll_context(post=post, user=self.voter)
        self.assertEqual(context["poll_total_votes"], 1)
        self.assertEqual(context["poll_user_option_id"], option.id)
        self.assertTrue(context["poll_show_results"])

    def test_author_cannot_vote_on_own_poll(self):
        post = create_post(
            user=self.author,
            body="My poll",
            poll_payload={"options": ["Yes", "No"], "duration_days": 1},
        )
        poll = Poll.objects.get(post=post)
        option = poll.options.first()
        with self.assertRaisesMessage(ValueError, "You can't vote on your own poll."):
            vote_on_poll(user=self.author, poll=poll, option=option)

    def test_validate_poll_payload_requires_two_choices(self):
        with self.assertRaises(Exception):
            validate_poll_payload(
                poll_payload={"options": ["Only one"], "duration_days": 1},
                body="",
            )

    def test_build_feed_item_includes_poll_context(self):
        post = create_post(
            user=self.author,
            body="Who wins?",
            poll_payload={"options": ["A", "B"], "duration_days": 1},
        )
        from pulse.selectors import build_feed_item, get_post_with_interactions

        post = get_post_with_interactions(post.id)
        post.comment_count = 0
        item = build_feed_item(
            post=post,
            user=self.voter,
            post_votes={},
            bookmarked_ids=set(),
            repost_counts={},
            user_reposted_ids=set(),
        )
        self.assertIn("poll", item)
        self.assertEqual(len(item["poll_options"]), 2)

    def test_parse_poll_options_from_post(self):
        payload = parse_poll_options_from_post(
            {
                "enable_poll": "1",
                "poll_option_0": " One ",
                "poll_option_1": "Two",
                "poll_option_2": "",
                "poll_days": "7",
            }
        )
        self.assertEqual(payload["options"], ["One", "Two"])
        self.assertEqual(payload["duration_days"], 7)
