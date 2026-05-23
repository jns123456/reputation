from django.test import Client, TestCase

from accounts.models import User
from comments.models import Comment, Vote
from comments.selectors import get_prediction_comment_threads
from comments.services import cast_vote, create_comment
from markets.models import Market
from predictions.models import Prediction


class PredictionThreadTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username="forecaster", password="pass")
        self.commenter = User.objects.create_user(username="debater", password="pass")
        self.replier = User.objects.create_user(username="replier", password="pass")
        self.market = Market.objects.create(
            external_id="thread-m1",
            title="Thread test market",
            slug="thread-test-market",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
        )
        self.prediction = Prediction.objects.create(
            user=self.author,
            market=self.market,
            predicted_outcome="Yes",
            confidence=0.7,
        )
        self.client = Client()

    def test_create_comment_on_prediction_thread(self):
        comment = create_comment(
            user=self.commenter,
            market=self.market,
            prediction=self.prediction,
            body="I disagree with this forecast.",
        )
        self.assertEqual(comment.prediction_id, self.prediction.id)
        self.assertIsNone(comment.parent_comment_id)

    def test_owner_cannot_top_level_comment_on_own_prediction(self):
        with self.assertRaisesMessage(
            ValueError,
            "You cannot comment on your own forecast. Reply to others instead.",
        ):
            create_comment(
                user=self.author,
                market=self.market,
                prediction=self.prediction,
                body="Talking to myself.",
            )

    def test_owner_can_reply_to_other_comment(self):
        parent = create_comment(
            user=self.commenter,
            market=self.market,
            prediction=self.prediction,
            body="What makes you so confident?",
        )
        reply = create_comment(
            user=self.author,
            market=self.market,
            body="Here is my reasoning.",
            parent_comment=parent,
        )
        self.assertEqual(reply.parent_comment_id, parent.id)

    def test_owner_cannot_reply_to_own_comment(self):
        parent = create_comment(
            user=self.commenter,
            market=self.market,
            prediction=self.prediction,
            body="Question for you.",
        )
        own_reply = create_comment(
            user=self.author,
            market=self.market,
            body="My answer.",
            parent_comment=parent,
        )
        with self.assertRaisesMessage(ValueError, "You cannot reply to your own comment."):
            create_comment(
                user=self.author,
                market=self.market,
                body="Following up on myself.",
                parent_comment=own_reply,
            )

    def test_owner_cannot_vote_on_own_prediction(self):
        with self.assertRaisesMessage(ValueError, "You cannot vote on your own forecast."):
            cast_vote(
                user=self.author,
                target_type=Vote.TargetType.PREDICTION,
                target_id=self.prediction.id,
                value=1,
            )

    def test_owner_cannot_top_level_comment_via_view(self):
        self.client.login(username="forecaster", password="pass")
        response = self.client.post(
            f"/comments/markets/{self.market.slug}/create/",
            {
                "body": "Self comment",
                "prediction": self.prediction.id,
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Comment.objects.filter(prediction=self.prediction).count(), 0)

    def test_nested_reply_links_to_same_prediction(self):
        parent = create_comment(
            user=self.commenter,
            market=self.market,
            prediction=self.prediction,
            body="Top-level comment",
        )
        reply = create_comment(
            user=self.replier,
            market=self.market,
            body="Nested reply",
            parent_comment=parent,
        )
        self.assertEqual(reply.prediction_id, self.prediction.id)
        self.assertEqual(reply.parent_comment_id, parent.id)

    def test_build_comment_forest_nests_replies(self):
        parent = create_comment(
            user=self.commenter,
            market=self.market,
            prediction=self.prediction,
            body="Parent",
        )
        create_comment(
            user=self.replier,
            market=self.market,
            body="Child",
            parent_comment=parent,
        )
        threads = get_prediction_comment_threads(self.prediction)
        self.assertEqual(len(threads), 1)
        self.assertEqual(len(threads[0].thread_replies), 1)

    def test_post_comment_via_view_returns_thread_partial(self):
        self.client.login(username="debater", password="pass")
        response = self.client.post(
            f"/comments/markets/{self.market.slug}/create/",
            {
                "body": "Via HTMX",
                "prediction": self.prediction.id,
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Via HTMX")
        self.assertEqual(Comment.objects.filter(prediction=self.prediction).count(), 1)

    def test_comment_requires_prediction(self):
        self.client.login(username="debater", password="pass")
        response = self.client.post(
            f"/comments/markets/{self.market.slug}/create/",
            {"body": "Orphan comment"},
        )
        self.assertEqual(response.status_code, 400)

    def test_vote_on_thread_comment(self):
        comment = create_comment(
            user=self.commenter,
            market=self.market,
            prediction=self.prediction,
            body="Vote me",
        )
        self.client.login(username="replier", password="pass")
        response = self.client.post(
            "/comments/vote/",
            {
                "target_type": Vote.TargetType.COMMENT,
                "target_id": comment.id,
                "value": "1",
                "layout": "vertical",
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        comment.refresh_from_db()
        self.assertEqual(comment.popularity_score, 1)

    def test_comment_threads_sorted_by_popularity(self):
        low = create_comment(
            user=self.commenter,
            market=self.market,
            prediction=self.prediction,
            body="Low score",
        )
        high = create_comment(
            user=self.replier,
            market=self.market,
            prediction=self.prediction,
            body="High score",
        )
        cast_vote(
            user=self.author,
            target_type=Vote.TargetType.COMMENT,
            target_id=high.id,
            value=1,
        )
        high.refresh_from_db()
        low.refresh_from_db()
        self.assertGreater(high.popularity_score, low.popularity_score)

        threads = get_prediction_comment_threads(self.prediction)
        self.assertEqual([thread.id for thread in threads], [high.id, low.id])

    def test_nested_replies_sorted_by_popularity(self):
        parent = create_comment(
            user=self.commenter,
            market=self.market,
            prediction=self.prediction,
            body="Parent",
        )
        low_reply = create_comment(
            user=self.replier,
            market=self.market,
            body="Low reply",
            parent_comment=parent,
        )
        high_reply = create_comment(
            user=self.author,
            market=self.market,
            body="High reply",
            parent_comment=parent,
        )
        cast_vote(
            user=self.commenter,
            target_type=Vote.TargetType.COMMENT,
            target_id=high_reply.id,
            value=1,
        )

        threads = get_prediction_comment_threads(self.prediction)
        reply_ids = [reply.id for reply in threads[0].thread_replies]
        self.assertEqual(reply_ids, [high_reply.id, low_reply.id])

    def test_comment_threads_tiebreak_by_author_reputation(self):
        self.commenter.profile.reputation_score = 50.0
        self.commenter.profile.save(update_fields=["reputation_score"])
        self.replier.profile.reputation_score = 10.0
        self.replier.profile.save(update_fields=["reputation_score"])

        low_rep = create_comment(
            user=self.replier,
            market=self.market,
            prediction=self.prediction,
            body="Lower reputation author",
        )
        high_rep = create_comment(
            user=self.commenter,
            market=self.market,
            prediction=self.prediction,
            body="Higher reputation author",
        )

        threads = get_prediction_comment_threads(self.prediction)
        self.assertEqual([thread.id for thread in threads], [high_rep.id, low_rep.id])
