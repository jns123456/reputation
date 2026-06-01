"""Tests for unified write-path anti-abuse guard."""

from django.core.cache import cache
from django.test import TestCase, override_settings

from accounts import abuse_services
from accounts.models import AbuseEvent
from accounts.write_guard import ContentRejected, guard_write_action
from comments.models import Vote
from comments.services import cast_vote, create_comment
from conftest import create_market, create_user
from predictions.services import create_prediction
from pulse.services import create_post, create_pulse_comment


@override_settings(ABUSE_WRITE_GUARD_ENABLED=True)
class WriteGuardServiceTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_create_comment_enforces_rate_limit(self):
        user = create_user(username="comment_guard")
        market = create_market(slug="comment-guard-market")
        author = create_user(username="forecast_author")
        prediction = create_prediction(
            user=author,
            market=market,
            predicted_outcome="Yes",
        )

        with override_settings(ABUSE_RATE_LIMITS={"comment": {"standard": (1, 3600)}}):
            create_comment(
                user=user,
                market=market,
                body="First thoughtful reply here",
                prediction=prediction,
            )
            with self.assertRaises(abuse_services.RateLimitExceeded):
                create_comment(
                    user=user,
                    market=market,
                    body="Second reply should be blocked",
                    prediction=prediction,
                )

    def test_create_comment_rejects_spam_content(self):
        user = create_user(username="spam_commenter")
        market = create_market(slug="spam-comment-market")
        author = create_user(username="spam_forecast_author")
        prediction = create_prediction(
            user=author,
            market=market,
            predicted_outcome="Yes",
        )
        body = "Clearly duplicated comment body for spam test"

        create_comment(
            user=user,
            market=market,
            body=body,
            prediction=prediction,
        )
        with self.assertRaises(ContentRejected):
            create_comment(
                user=user,
                market=market,
                body=body,
                prediction=prediction,
            )

    def test_create_prediction_enforces_rate_limit(self):
        user = create_user(username="forecast_guard")
        market_one = create_market(slug="forecast-guard-one", external_id="fg-1")
        market_two = create_market(slug="forecast-guard-two", external_id="fg-2")

        with override_settings(ABUSE_RATE_LIMITS={"prediction": {"standard": (1, 3600)}}):
            create_prediction(user=user, market=market_one, predicted_outcome="Yes")
            with self.assertRaises(abuse_services.RateLimitExceeded):
                create_prediction(user=user, market=market_two, predicted_outcome="No")

    def test_create_prediction_assesses_reasoning_text(self):
        user = create_user(username="reasoning_guard")
        market_one = create_market(slug="reasoning-guard-one", external_id="rg-1")
        market_two = create_market(slug="reasoning-guard-two", external_id="rg-2")
        reasoning = "Repeated reasoning block for guard test"

        create_prediction(
            user=user,
            market=market_one,
            predicted_outcome="Yes",
            reasoning=reasoning,
        )
        with self.assertRaises(ContentRejected):
            create_prediction(
                user=user,
                market=market_two,
                predicted_outcome="No",
                reasoning=reasoning,
            )

    def test_cast_vote_enforces_rate_limit(self):
        author = create_user(username="vote_author")
        voter = create_user(username="vote_guard")
        market = create_market(slug="vote-guard-market", external_id="vg-1")
        prediction = create_prediction(user=author, market=market, predicted_outcome="Yes")

        with override_settings(ABUSE_RATE_LIMITS={"vote": {"standard": (1, 3600)}}):
            cast_vote(
                user=voter,
                target_type=Vote.TargetType.PREDICTION,
                target_id=prediction.id,
                value=1,
            )
            with self.assertRaises(abuse_services.RateLimitExceeded):
                cast_vote(
                    user=voter,
                    target_type=Vote.TargetType.PREDICTION,
                    target_id=prediction.id,
                    value=-1,
                )

    def test_create_post_enforces_rate_limit(self):
        user = create_user(username="post_guard")

        with override_settings(ABUSE_RATE_LIMITS={"post": {"standard": (1, 3600)}}):
            create_post(user=user, body="First forum post with enough text")
            with self.assertRaises(abuse_services.RateLimitExceeded):
                create_post(user=user, body="Second forum post blocked by guard")

    def test_create_pulse_comment_rejects_duplicate_content(self):
        author = create_user(username="pulse_author")
        commenter = create_user(username="pulse_dup")
        post = create_post(user=author, body="Original forum post body")

        create_pulse_comment(
            user=commenter,
            post=post,
            body="Unique comment text here",
        )
        with self.assertRaises(ContentRejected):
            create_pulse_comment(
                user=commenter,
                post=post,
                body="Unique comment text here",
            )

    def test_guard_can_be_disabled_via_settings(self):
        user = create_user(username="disabled_guard")
        with override_settings(
            ABUSE_WRITE_GUARD_ENABLED=False,
            ABUSE_RATE_LIMITS={"comment": {"standard": (1, 3600)}},
        ):
            guard_write_action(action="comment", user=user, text="ignored when disabled")
            guard_write_action(action="comment", user=user, text="still ignored")
        self.assertFalse(
            AbuseEvent.objects.filter(
                event_type=AbuseEvent.EventType.RATE_LIMITED,
                user=user,
            ).exists()
        )
