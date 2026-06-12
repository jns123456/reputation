"""Head-to-head duel records, rematch prefill, and spectator access."""

from django.test import TestCase
from django.urls import reverse

from challenges.models import Challenge, ChallengeParticipant
from challenges.selectors import get_head_to_head_record
from conftest import create_user


def _completed_duel(user_a, user_b, *, winner=None, n=0):
    challenge = Challenge.objects.create(
        creator=user_a,
        title=f"Duel {n}",
        status=Challenge.Status.COMPLETED,
        winner=winner,
    )
    for user in (user_a, user_b):
        ChallengeParticipant.objects.create(
            challenge=challenge,
            user=user,
            status=ChallengeParticipant.Status.ACCEPTED,
        )
    return challenge


class HeadToHeadTests(TestCase):
    def setUp(self):
        self.alice = create_user("h2halice")
        self.bob = create_user("h2hbob")

    def test_record_counts_wins_losses_ties(self):
        _completed_duel(self.alice, self.bob, winner=self.alice, n=1)
        _completed_duel(self.alice, self.bob, winner=self.bob, n=2)
        _completed_duel(self.alice, self.bob, winner=None, n=3)

        record = get_head_to_head_record(user=self.alice, opponent=self.bob)
        self.assertEqual(record, {"wins": 1, "losses": 1, "ties": 1, "total": 3})

    def test_group_challenges_excluded_from_duel_record(self):
        carol = create_user("h2hcarol")
        challenge = _completed_duel(self.alice, self.bob, winner=self.alice, n=4)
        ChallengeParticipant.objects.create(
            challenge=challenge,
            user=carol,
            status=ChallengeParticipant.Status.ACCEPTED,
        )
        record = get_head_to_head_record(user=self.alice, opponent=self.bob)
        self.assertEqual(record["total"], 0)

    def test_spectator_can_view_completed_challenge(self):
        challenge = _completed_duel(self.alice, self.bob, winner=self.alice, n=5)
        spectator = create_user("h2hspectator")
        self.client.force_login(spectator)
        response = self.client.get(
            reverse("challenges:detail", kwargs={"pk": challenge.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_spectator"])

    def test_rematch_prefills_opponents(self):
        challenge = _completed_duel(self.alice, self.bob, winner=self.bob, n=6)
        self.client.force_login(self.alice)
        response = self.client.get(
            reverse("challenges:create"), {"rematch": str(challenge.pk)}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form"].fields["opponents"].initial
            or response.context["form"].initial.get("opponents"),
            [str(self.bob.id)],
        )
