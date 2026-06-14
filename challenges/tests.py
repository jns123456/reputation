from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import User, UserFollow
from accounts.follow_selectors import are_mutual_followers, get_mutual_followers
from challenges.models import Challenge, ChallengeParticipant, MAX_CHALLENGE_MARKETS
from challenges.selectors import get_challenge_leaderboard, get_challenge_standings
from challenges.services import (
    accept_challenge,
    create_challenge,
    decline_challenge,
)
from markets.models import Market
from predictions.services import create_prediction


from conftest import create_user


class MutualFollowTests(TestCase):
    def setUp(self):
        self.alice = create_user("alice")
        self.bob = create_user("bob")
        self.carol = create_user("carol")

    def test_mutual_followers(self):
        UserFollow.objects.create(follower=self.alice, following=self.bob)
        UserFollow.objects.create(follower=self.bob, following=self.alice)
        UserFollow.objects.create(follower=self.alice, following=self.carol)

        self.assertTrue(are_mutual_followers(self.alice, self.bob))
        self.assertFalse(are_mutual_followers(self.alice, self.carol))
        mutual = list(get_mutual_followers(self.alice))
        self.assertEqual(len(mutual), 1)
        self.assertEqual(mutual[0].username, "bob")


class ChallengeCreateTests(TestCase):
    def setUp(self):
        self.alice = create_user("alice")
        self.bob = create_user("bob")
        UserFollow.objects.create(follower=self.alice, following=self.bob)
        UserFollow.objects.create(follower=self.bob, following=self.alice)
        self.market1 = Market.objects.create(
            external_id="m1",
            title="Event 1",
            slug="event-1",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )
        self.market2 = Market.objects.create(
            external_id="m2",
            title="Event 2",
            slug="event-2",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )

    def test_create_challenge_success(self):
        challenge = create_challenge(
            creator=self.alice,
            title="Head to head",
            market_ids=[self.market1.id, self.market2.id],
            opponent_ids=[self.bob.id],
        )
        self.assertEqual(challenge.status, Challenge.Status.PENDING)
        self.assertEqual(challenge.challenge_markets.count(), 2)
        self.assertEqual(challenge.participants.count(), 2)
        creator_part = challenge.participants.get(user=self.alice)
        self.assertEqual(creator_part.status, ChallengeParticipant.Status.ACCEPTED)

    def test_create_challenge_without_mutual_follow(self):
        carol = create_user("carol")
        challenge = create_challenge(
            creator=self.alice,
            title="Open invite",
            market_ids=[self.market1.id],
            opponent_ids=[carol.id],
        )
        self.assertEqual(challenge.participants.filter(user=carol).count(), 1)

    def test_create_challenge_view_accepts_single_market(self):
        self.client.force_login(self.alice)
        response = self.client.post(
            "/challenges/new/",
            {
                "title": "Quick duel",
                "opponents": [str(self.bob.id)],
                "markets": [str(self.market1.id)],
            },
        )
        self.assertEqual(response.status_code, 302)
        challenge = Challenge.objects.get(creator=self.alice, title="Quick duel")
        self.assertEqual(challenge.challenge_markets.count(), 1)

    def test_rejects_more_than_ten_markets(self):
        market_ids = []
        for i in range(MAX_CHALLENGE_MARKETS + 1):
            m = Market.objects.create(
                external_id=f"mx-{i}",
                title=f"Event {i}",
                slug=f"event-max-{i}",
                status=Market.Status.OPEN,
                outcomes=[{"label": "Yes"}],
                current_probability={"Yes": 0.5},
            )
            market_ids.append(m.id)
        with self.assertRaises(ValidationError):
            create_challenge(
                creator=self.alice,
                title="",
                market_ids=market_ids,
                opponent_ids=[self.bob.id],
            )


class ChallengeFlowTests(TestCase):
    def setUp(self):
        self.alice = create_user("alice")
        self.bob = create_user("bob")
        UserFollow.objects.create(follower=self.alice, following=self.bob)
        UserFollow.objects.create(follower=self.bob, following=self.alice)
        self.market = Market.objects.create(
            external_id="m1",
            title="Event 1",
            slug="event-1",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )
        self.challenge = create_challenge(
            creator=self.alice,
            title="Duel",
            market_ids=[self.market.id],
            opponent_ids=[self.bob.id],
        )

    def test_accept_activates_challenge(self):
        accept_challenge(challenge=self.challenge, user=self.bob)
        self.challenge.refresh_from_db()
        self.assertEqual(self.challenge.status, Challenge.Status.ACTIVE)
        self.assertIsNotNone(self.challenge.started_at)

    def test_decline_without_accept_keeps_pending(self):
        decline_challenge(challenge=self.challenge, user=self.bob)
        self.challenge.refresh_from_db()
        self.assertEqual(self.challenge.status, Challenge.Status.PENDING)

    def test_standings_zero_before_active(self):
        standings = get_challenge_standings(self.challenge)
        self.assertEqual(len(standings), 1)
        self.assertEqual(standings[0]["realized_points"], 0)
        self.assertEqual(standings[0]["unrealized_points"], 0)
        self.assertEqual(standings[0]["total_points"], 0)


class PriorPredictionChallengeTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="pass")
        self.bob = User.objects.create_user(username="bob", password="pass")
        UserFollow.objects.create(follower=self.alice, following=self.bob)
        UserFollow.objects.create(follower=self.bob, following=self.alice)
        self.market = Market.objects.create(
            external_id="m-prior",
            title="Prior event",
            slug="prior-event",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.9, "No": 0.1},
        )

    def test_pre_challenge_forecast_counts_in_standings(self):
        from predictions.services import create_prediction, resolve_market_predictions

        prediction = create_prediction(
            user=self.bob,
            market=self.market,
            predicted_outcome="Yes",
        )
        original_created_at = prediction.created_at

        challenge = create_challenge(
            creator=self.alice,
            title="Retroactive",
            market_ids=[self.market.id],
            opponent_ids=[self.bob.id],
        )
        accept_challenge(challenge=challenge, user=self.bob)
        challenge.refresh_from_db()

        self.assertLess(prediction.created_at, challenge.started_at)

        self.market.status = Market.Status.RESOLVED
        self.market.resolved_outcome = "Yes"
        self.market.save()
        resolve_market_predictions(self.market)

        prediction.refresh_from_db()
        self.assertEqual(prediction.created_at, original_created_at)

        standings = get_challenge_standings(challenge)
        bob_row = next(row for row in standings if row["participant"].user_id == self.bob.id)
        self.assertEqual(bob_row["realized_points"], 10)
        self.assertEqual(bob_row["unrealized_points"], 0)
        self.assertEqual(bob_row["total_points"], 10)

    def test_challenge_completion_awards_winner_badge(self):
        from accounts.models import UserAchievement
        from challenges.services import check_challenge_completion
        from predictions.services import create_prediction, resolve_market_predictions

        create_prediction(
            user=self.bob,
            market=self.market,
            predicted_outcome="Yes",
        )
        challenge = create_challenge(
            creator=self.alice,
            title="Badge duel",
            market_ids=[self.market.id],
            opponent_ids=[self.bob.id],
        )
        accept_challenge(challenge=challenge, user=self.bob)

        self.market.status = Market.Status.RESOLVED
        self.market.resolved_outcome = "Yes"
        self.market.save()
        resolve_market_predictions(self.market)
        check_challenge_completion(market=self.market)

        challenge.refresh_from_db()
        self.assertEqual(challenge.winner, self.bob)
        self.assertTrue(
            UserAchievement.objects.filter(
                user=self.bob, code="challenge_win_1"
            ).exists()
        )

    def test_pre_challenge_forecast_counts_as_unrealized_while_open(self):
        create_prediction(
            user=self.bob,
            market=self.market,
            predicted_outcome="Yes",
        )
        self.market.current_probability = {"Yes": 0.5, "No": 0.5}
        self.market.save(update_fields=["current_probability"])

        challenge = create_challenge(
            creator=self.alice,
            title="Retroactive open",
            market_ids=[self.market.id],
            opponent_ids=[self.bob.id],
        )
        accept_challenge(challenge=challenge, user=self.bob)

        standings = get_challenge_standings(challenge)
        bob_row = next(row for row in standings if row["participant"].user_id == self.bob.id)
        self.assertEqual(bob_row["realized_points"], 0)
        self.assertEqual(bob_row["unrealized_points"], -40)
        self.assertEqual(bob_row["total_points"], -40)

    def test_exit_before_accept_does_not_count_as_realized(self):
        from predictions.services import create_prediction, exit_prediction

        prediction = create_prediction(
            user=self.bob,
            market=self.market,
            predicted_outcome="Yes",
        )
        self.market.current_probability = {"Yes": 0.55, "No": 0.45}
        self.market.save(update_fields=["current_probability"])
        exit_prediction(prediction=prediction, user=self.bob)

        challenge = create_challenge(
            creator=self.alice,
            title="Clean join",
            market_ids=[self.market.id],
            opponent_ids=[self.bob.id],
        )
        accept_challenge(challenge=challenge, user=self.bob)

        standings = get_challenge_standings(challenge)
        bob_row = next(row for row in standings if row["participant"].user_id == self.bob.id)
        self.assertEqual(bob_row["realized_points"], 0)
        self.assertEqual(bob_row["unrealized_points"], 0)
        self.assertEqual(bob_row["total_points"], 0)


class ResolutionSnapshotTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="pass")
        self.bob = User.objects.create_user(username="bob", password="pass")
        UserFollow.objects.create(follower=self.alice, following=self.bob)
        UserFollow.objects.create(follower=self.bob, following=self.alice)
        self.market1 = Market.objects.create(
            external_id="ms1",
            title="Event A",
            slug="event-a",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )
        self.market2 = Market.objects.create(
            external_id="ms2",
            title="Event B",
            slug="event-b",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )

    def test_snapshots_include_cumulative_standings(self):
        from django.utils import timezone
        from predictions.services import create_prediction, resolve_market_predictions
        from challenges.selectors import get_challenge_resolution_snapshots

        create_prediction(user=self.alice, market=self.market1, predicted_outcome="Yes")
        create_prediction(user=self.bob, market=self.market1, predicted_outcome="No")
        create_prediction(user=self.alice, market=self.market2, predicted_outcome="Yes")
        create_prediction(user=self.bob, market=self.market2, predicted_outcome="Yes")

        challenge = create_challenge(
            creator=self.alice,
            title="Multi",
            market_ids=[self.market1.id, self.market2.id],
            opponent_ids=[self.bob.id],
        )
        accept_challenge(challenge=challenge, user=self.bob)

        self.market1.status = Market.Status.RESOLVED
        self.market1.resolved_outcome = "Yes"
        self.market1.resolution_date = timezone.now()
        self.market1.save()
        resolve_market_predictions(self.market1)

        self.market2.status = Market.Status.RESOLVED
        self.market2.resolved_outcome = "Yes"
        self.market2.resolution_date = timezone.now()
        self.market2.save()
        resolve_market_predictions(self.market2)

        snapshots = get_challenge_resolution_snapshots(challenge)
        self.assertEqual(len(snapshots), 2)
        self.assertEqual(len(snapshots[0]["standings"]), 2)
        self.assertEqual(len(snapshots[1]["standings"]), 2)
        alice_after_two = next(
            row for row in snapshots[1]["standings"]
            if row["participant"].user_id == self.alice.id
        )
        self.assertGreater(alice_after_two["reputation_points"], 0)


class ChallengeLeaderboardTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="pass")
        self.bob = User.objects.create_user(username="bob", password="pass")
        UserFollow.objects.create(follower=self.alice, following=self.bob)
        UserFollow.objects.create(follower=self.bob, following=self.alice)
        self.market = Market.objects.create(
            external_id="m-open",
            title="Open event",
            slug="open-event",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.4, "No": 0.6},
        )

    def test_leaderboard_includes_invited_participants_before_start(self):
        challenge = create_challenge(
            creator=self.alice,
            title="Pending duel",
            market_ids=[self.market.id],
            opponent_ids=[self.bob.id],
        )
        leaderboard = get_challenge_leaderboard(challenge)
        self.assertEqual(len(leaderboard), 2)
        self.assertTrue(all(row["total_points"] == 0 for row in leaderboard))

    def test_unrealized_points_use_open_forecast_logic(self):
        from predictions.services import create_prediction

        create_prediction(
            user=self.alice,
            market=self.market,
            predicted_outcome="Yes",
        )
        self.market.current_probability = {"Yes": 0.5, "No": 0.5}
        self.market.save(update_fields=["current_probability"])

        challenge = create_challenge(
            creator=self.alice,
            title="Live duel",
            market_ids=[self.market.id],
            opponent_ids=[self.bob.id],
        )
        accept_challenge(challenge=challenge, user=self.bob)

        standings = get_challenge_standings(challenge)
        alice_row = next(row for row in standings if row["participant"].user_id == self.alice.id)
        self.assertEqual(alice_row["realized_points"], 0)
        self.assertEqual(alice_row["unrealized_points"], 10)
        self.assertEqual(alice_row["total_points"], 10)


class ChallengeForecastRulesTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="pass")
        self.bob = User.objects.create_user(username="bob", password="pass")
        from accounts.models import UserFollow

        UserFollow.objects.create(follower=self.alice, following=self.bob)
        UserFollow.objects.create(follower=self.bob, following=self.alice)
        self.market = Market.objects.create(
            external_id="cf-m1",
            title="Challenge forecast event",
            slug="challenge-forecast-event",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )
        self.challenge = create_challenge(
            creator=self.alice,
            title="Forecast rules duel",
            market_ids=[self.market.id],
            opponent_ids=[self.bob.id],
        )
        accept_challenge(challenge=self.challenge, user=self.bob)

    def test_duplicate_forecast_error_mentions_challenge(self):
        create_prediction(
            user=self.alice,
            market=self.market,
            predicted_outcome="Yes",
        )
        from predictions.services import build_duplicate_forecast_error, resolve_market_predictions

        message = build_duplicate_forecast_error(user=self.alice, market=self.market)
        self.assertIn("Forecast rules duel", message)
        self.assertIn("global reputation", message.lower())

    def test_resolved_challenge_forecast_updates_global_and_standings(self):
        from predictions.services import resolve_market_predictions

        create_prediction(
            user=self.alice,
            market=self.market,
            predicted_outcome="Yes",
        )
        rep_before = self.alice.profile.reputation_points
        self.market.status = Market.Status.RESOLVED
        self.market.resolved_outcome = "Yes"
        self.market.save()
        resolve_market_predictions(self.market)

        self.alice.profile.refresh_from_db()
        self.assertGreater(self.alice.profile.reputation_points, rep_before)

        standings = get_challenge_standings(self.challenge)
        alice_row = next(row for row in standings if row["participant"].user_id == self.alice.id)
        self.assertGreater(alice_row["realized_points"], 0)


class ChallengeEventSortTests(TestCase):
    def test_markets_sorted_by_soonest_close_date(self):
        from datetime import timedelta

        from challenges.views import _sort_challenge_markets_by_expiration

        soon = Market.objects.create(
            external_id="sort-soon",
            title="Soon",
            slug="sort-soon",
            status=Market.Status.OPEN,
            close_date=timezone.now() + timedelta(days=1),
        )
        later = Market.objects.create(
            external_id="sort-later",
            title="Later",
            slug="sort-later",
            status=Market.Status.OPEN,
            close_date=timezone.now() + timedelta(days=30),
        )
        no_date = Market.objects.create(
            external_id="sort-none",
            title="No date",
            slug="sort-none",
            status=Market.Status.OPEN,
        )

        ordered = _sort_challenge_markets_by_expiration([later, no_date, soon])
        self.assertEqual([market.slug for market in ordered], ["sort-soon", "sort-later", "sort-none"])


class ChallengeNotificationTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="pass")
        self.bob = User.objects.create_user(username="bob", password="pass")
        UserFollow.objects.create(follower=self.alice, following=self.bob)
        UserFollow.objects.create(follower=self.bob, following=self.alice)
        self.market = Market.objects.create(
            external_id="m1",
            title="Event 1",
            slug="event-1",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )
        self.challenge = create_challenge(
            creator=self.alice,
            title="Duel",
            market_ids=[self.market.id],
            opponent_ids=[self.bob.id],
        )

    def test_invitation_notification_on_create(self):
        from accounts.models import Notification

        self.assertTrue(
            Notification.objects.filter(
                recipient=self.bob,
                notification_type=Notification.NotificationType.CHALLENGE_INVITATION,
                challenge=self.challenge,
            ).exists()
        )

    def test_market_resolved_notification(self):
        from accounts.models import Notification
        from challenges.notification_services import notify_challenge_market_resolved

        accept_challenge(challenge=self.challenge, user=self.bob)
        self.challenge.refresh_from_db()
        self.market.status = Market.Status.RESOLVED
        self.market.resolved_outcome = "Yes"
        self.market.save()

        notify_challenge_market_resolved(challenge=self.challenge, market=self.market)

        for user in (self.alice, self.bob):
            self.assertTrue(
                Notification.objects.filter(
                    recipient=user,
                    notification_type=Notification.NotificationType.CHALLENGE_MARKET_RESOLVED,
                    challenge=self.challenge,
                    market=self.market,
                ).exists()
            )

    def test_accept_marks_invitation_notification_read(self):
        from accounts.models import Notification

        notification = Notification.objects.get(
            recipient=self.bob,
            notification_type=Notification.NotificationType.CHALLENGE_INVITATION,
            challenge=self.challenge,
        )
        accept_challenge(challenge=self.challenge, user=self.bob)
        notification.refresh_from_db()
        self.assertIsNotNone(notification.read_at)

    def test_accept_notifies_creator(self):
        from accounts.models import Notification

        accept_challenge(challenge=self.challenge, user=self.bob)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.alice,
                actor=self.bob,
                notification_type=Notification.NotificationType.CHALLENGE_ACCEPTED,
                challenge=self.challenge,
            ).exists()
        )


class ChallengeInvitationListTests(TestCase):
    def setUp(self):
        self.alice = create_user("alice")
        self.bob = create_user("bob")
        UserFollow.objects.create(follower=self.alice, following=self.bob)
        UserFollow.objects.create(follower=self.bob, following=self.alice)
        self.market = Market.objects.create(
            external_id="m-inv",
            title="Event 1",
            slug="event-inv",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}],
            current_probability={"Yes": 0.5},
        )
        self.challenge = create_challenge(
            creator=self.alice,
            title="Mundial",
            market_ids=[self.market.id],
            opponent_ids=[self.bob.id],
        )

    def test_list_shows_pending_invitation_with_actions(self):
        self.client.force_login(self.bob)
        response = self.client.get("/challenges/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pending invitations")
        self.assertContains(response, "Mundial")
        self.assertContains(response, "Accept")
        self.assertContains(response, "Decline")

    def test_decline_from_list(self):
        self.client.force_login(self.bob)
        response = self.client.post(f"/challenges/{self.challenge.pk}/decline/")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            ChallengeParticipant.objects.filter(
                user=self.bob,
                challenge=self.challenge,
                status=ChallengeParticipant.Status.INVITED,
            ).exists()
        )

class ChallengeGroupTests(TestCase):
    def setUp(self):
        from conftest import create_user

        self.alice = create_user("alice")
        self.bob = create_user("bob")
        self.carol = create_user("carol")
        UserFollow.objects.create(follower=self.alice, following=self.bob)
        UserFollow.objects.create(follower=self.bob, following=self.alice)
        UserFollow.objects.create(follower=self.alice, following=self.carol)
        UserFollow.objects.create(follower=self.carol, following=self.alice)

    def test_create_group_success(self):
        from challenges.services import create_challenge_group

        group = create_challenge_group(
            owner=self.alice,
            name="Weekend crew",
            member_ids=[self.bob.id, self.carol.id],
        )
        self.assertEqual(group.name, "Weekend crew")
        self.assertEqual(group.members.count(), 2)

    def test_create_group_without_mutual_follow(self):
        from challenges.services import create_challenge_group

        dave = create_user("dave")
        group = create_challenge_group(
            owner=self.alice,
            name="Open crew",
            member_ids=[dave.id],
        )
        self.assertEqual(group.members.count(), 1)
        self.assertEqual(group.members.get().username, "dave")

    def test_group_list_and_create_views(self):
        from challenges.services import create_challenge_group

        create_challenge_group(
            owner=self.alice,
            name="Friends",
            member_ids=[self.bob.id],
        )
        self.client.force_login(self.alice)
        response = self.client.get("/challenges/groups/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Friends")

        response = self.client.post(
            "/challenges/groups/new/",
            {"name": "More friends", "members": [str(self.carol.id)]},
        )
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get("/challenges/groups/"), "More friends")

    def test_create_challenge_shows_group_quick_select(self):
        from challenges.services import create_challenge_group

        create_challenge_group(
            owner=self.alice,
            name="Quick crew",
            member_ids=[self.bob.id],
        )
        self.client.force_login(self.alice)
        response = self.client.get("/challenges/new/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Quick crew")
        self.assertContains(response, "Saved groups")
        self.assertContains(response, "Categories")

    def test_group_challenge_activates_on_first_accept(self):
        from challenges.services import create_challenge_group, create_challenge

        dave = create_user("dave")
        eve = create_user("eve")
        for user in (dave, eve):
            UserFollow.objects.create(follower=self.alice, following=user)
            UserFollow.objects.create(follower=user, following=self.alice)

        group = create_challenge_group(
            owner=self.alice,
            name="Squad",
            member_ids=[self.bob.id, dave.id, eve.id],
        )
        market = Market.objects.create(
            external_id="mg1",
            title="Group event",
            slug="group-event",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )
        challenge = create_challenge(
            creator=self.alice,
            title="Group duel",
            market_ids=[market.id],
            opponent_ids=[self.bob.id, dave.id, eve.id],
            challenge_group=group,
        )
        self.assertEqual(challenge.status, Challenge.Status.PENDING)

        accept_challenge(challenge=challenge, user=self.bob)
        challenge.refresh_from_db()
        self.assertEqual(challenge.status, Challenge.Status.ACTIVE)

        invited = challenge.participants.filter(status=ChallengeParticipant.Status.INVITED)
        self.assertEqual(invited.count(), 2)

    def test_individual_multi_opponent_waits_for_all_responses(self):
        from challenges.services import create_challenge

        dave = create_user("dave")
        eve = create_user("eve")
        for user in (dave, eve):
            UserFollow.objects.create(follower=self.alice, following=user)
            UserFollow.objects.create(follower=user, following=self.alice)

        market = Market.objects.create(
            external_id="mg2",
            title="Multi event",
            slug="multi-event",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )
        challenge = create_challenge(
            creator=self.alice,
            title="Multi duel",
            market_ids=[market.id],
            opponent_ids=[self.bob.id, dave.id, eve.id],
        )

        accept_challenge(challenge=challenge, user=self.bob)
        challenge.refresh_from_db()
        self.assertEqual(challenge.status, Challenge.Status.PENDING)

        decline_challenge(challenge=challenge, user=dave)
        decline_challenge(challenge=challenge, user=eve)
        challenge.refresh_from_db()
        self.assertEqual(challenge.status, Challenge.Status.ACTIVE)

    def test_create_challenge_view_with_group(self):
        from challenges.services import create_challenge_group

        group = create_challenge_group(
            owner=self.alice,
            name="View squad",
            member_ids=[self.bob.id, self.carol.id],
        )
        market = Market.objects.create(
            external_id="vg1",
            title="View event",
            slug="view-event",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )
        self.client.force_login(self.alice)
        response = self.client.post(
            "/challenges/new/",
            {
                "title": "Group via form",
                "challenge_group": str(group.pk),
                "markets": [str(market.id)],
            },
        )
        self.assertEqual(response.status_code, 302)
        challenge = Challenge.objects.get(creator=self.alice, title="Group via form")
        self.assertEqual(challenge.challenge_group_id, group.pk)
        self.assertEqual(
            challenge.participants.filter(status=ChallengeParticipant.Status.INVITED).count(),
            2,
        )


class MarketSearchTests(TestCase):
    def setUp(self):
        self.user = create_user("alice")
        self.market_a = Market.objects.create(
            external_id="ma",
            title="Bitcoin price 2026",
            slug="bitcoin-price-2026",
            category="Crypto",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}],
            current_probability={"Yes": 0.5},
        )
        self.market_b = Market.objects.create(
            external_id="mb",
            title="US election winner",
            slug="us-election-winner",
            category="Politics",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}],
            current_probability={"Yes": 0.5},
        )
        Market.objects.create(
            external_id="mc",
            title="Closed market",
            slug="closed-market",
            status=Market.Status.CLOSED,
            outcomes=[{"label": "Yes"}],
            current_probability={"Yes": 0.5},
        )

    def test_search_open_markets_filters_by_title(self):
        from challenges.selectors import search_open_markets_for_challenge

        results = list(search_open_markets_for_challenge(query="bitcoin"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, self.market_a.id)

    def test_search_includes_selected_markets(self):
        from challenges.selectors import search_open_markets_for_challenge

        results = list(
            search_open_markets_for_challenge(
                query="zzzzz",
                selected_ids=[self.market_b.id],
            )
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, self.market_b.id)

    def test_market_search_view(self):
        self.client.force_login(self.user)
        response = self.client.get(
            "/challenges/markets/search/",
            {"q": "election"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "US election winner")
        self.assertNotContains(response, "Bitcoin price 2026")

    def test_market_browse_categories_view(self):
        from markets.models import Market

        self.market_a.canonical_category_slug = "crypto"
        self.market_a.save(update_fields=["canonical_category_slug"])

        self.client.force_login(self.user)
        response = self.client.get("/challenges/markets/browse/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Categories")

    def test_market_browse_category_view(self):
        self.market_a.canonical_category_slug = "crypto"
        self.market_a.save(update_fields=["canonical_category_slug"])

        self.client.force_login(self.user)
        response = self.client.get(
            "/challenges/markets/browse/",
            {"category": "crypto"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bitcoin price 2026")
        self.assertContains(response, "All categories")

    def test_market_browse_soccer_match_card_shows_kickoff_and_colored_outcomes(self):
        from django.utils import timezone

        kickoff = timezone.datetime(2026, 6, 14, 17, 0, tzinfo=timezone.utc)
        Market.objects.create(
            external_id="wc-match:picker-soccer",
            title="Germany vs. Curaçao",
            slug="germany-vs-curacao-picker",
            status=Market.Status.OPEN,
            canonical_category_slug="fifa-world-cup-2026",
            close_date=kickoff,
            game_start_time=kickoff,
            polymarket_raw={
                "market_kind": "soccer_match_3way",
                "team_a": "Germany",
                "team_b": "Curaçao",
                "kickoff_at": kickoff.isoformat(),
            },
            polymarket_event_raw={"tags": [{"slug": "fifa-world-cup"}]},
            outcomes=[{"label": "Germany"}, {"label": "Draw"}, {"label": "Curaçao"}],
            current_probability={"Germany": 0.94, "Draw": 0.04, "Curaçao": 0.02},
        )

        self.client.force_login(self.user)
        response = self.client.get(
            "/challenges/markets/browse/",
            {"category": "fifa-world-cup-2026"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Germany vs. Curaçao")
        self.assertContains(response, "UTC")
        self.assertContains(response, "border-emerald-200 bg-emerald-50")
        self.assertContains(response, "border-amber-200 bg-amber-50")
        self.assertContains(response, "border-rose-200 bg-rose-50")
        self.assertContains(response, "3-way result")

    def test_market_browse_h2h_match_card_shows_kickoff_and_colored_outcomes(self):
        from django.utils import timezone

        kickoff = timezone.datetime(2026, 6, 14, 20, 0, tzinfo=timezone.utc)
        Market.objects.create(
            external_id="h2h-match:picker-nba",
            title="Lakers vs. Celtics",
            slug="lakers-vs-celtics-picker",
            status=Market.Status.OPEN,
            canonical_category_slug="sports",
            close_date=kickoff,
            game_start_time=kickoff,
            polymarket_raw={
                "market_kind": "h2h_match_2way",
                "team_a": "Lakers",
                "team_b": "Celtics",
            },
            polymarket_event_raw={"tags": [{"slug": "nba"}]},
            outcomes=[{"label": "Lakers"}, {"label": "Celtics"}],
            current_probability={"Lakers": 0.58, "Celtics": 0.42},
        )

        self.client.force_login(self.user)
        response = self.client.get(
            "/challenges/markets/browse/",
            {"category": "sports", "area": "nba"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lakers vs. Celtics")
        self.assertContains(response, "UTC")
        self.assertContains(response, "border-emerald-200 bg-emerald-50")
        self.assertContains(response, "border-rose-200 bg-rose-50")
        self.assertContains(response, "Match winner")

    def test_market_browse_binary_market_shows_yes_no_colors(self):
        self.market_a.canonical_category_slug = "crypto"
        self.market_a.outcomes = [{"label": "Yes"}, {"label": "No"}]
        self.market_a.current_probability = {"Yes": 0.62, "No": 0.38}
        self.market_a.save(update_fields=["canonical_category_slug", "outcomes", "current_probability"])

        self.client.force_login(self.user)
        response = self.client.get(
            "/challenges/markets/browse/",
            {"category": "crypto"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bitcoin price 2026")
        self.assertContains(response, "pr-neo-outcome--yes")
        self.assertContains(response, "pr-neo-outcome--no")


class ChallengeHowItWorksViewTests(TestCase):
    def test_page_loads_without_login(self):
        response = self.client.get("/challenges/how-it-works/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "How challenges work")

    def test_page_mentions_existing_forecasts(self):
        response = self.client.get("/challenges/how-it-works/")
        self.assertContains(response, "existing open forecast counts automatically", html=False)


class ChallengeListViewTests(TestCase):
    def setUp(self):
        self.alice = create_user("alice")
        self.active = Challenge.objects.create(
            creator=self.alice,
            title="Active duel",
            status=Challenge.Status.ACTIVE,
        )
        self.completed = Challenge.objects.create(
            creator=self.alice,
            title="Finished duel",
            status=Challenge.Status.COMPLETED,
        )

    def test_list_defaults_to_active_filter(self):
        self.client.force_login(self.alice)
        response = self.client.get("/challenges/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Active duel")
        self.assertNotContains(response, "Finished duel")

    def test_list_status_all_shows_every_challenge(self):
        self.client.force_login(self.alice)
        response = self.client.get("/challenges/?status=all")
        self.assertContains(response, "Active duel")
        self.assertContains(response, "Finished duel")

    def test_list_status_active_matches_default(self):
        self.client.force_login(self.alice)
        response = self.client.get("/challenges/?status=active")
        self.assertContains(response, "Active duel")
        self.assertNotContains(response, "Finished duel")

