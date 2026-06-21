from django.core.cache import cache
from django.test import TestCase

from accounts.models import User, UserProfile
from reputation.platform_rank import (
    REPUTATION_RELATIVE,
    build_platform_top_rank_index,
    get_user_platform_top_rank_badges,
)


class PlatformRankBadgeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.leader = User.objects.create_user(username="leader", password="pass")
        self.second = User.objects.create_user(username="second", password="pass")
        self.outside = User.objects.create_user(username="outside", password="pass")

        UserProfile.objects.filter(user=self.leader).update(
            reputation_points=120,
            reputation_score=40.0,
            scored_forecast_count=12,
            popularity_score=50,
            popularity_points=500,
        )
        UserProfile.objects.filter(user=self.second).update(
            reputation_points=300,
            reputation_score=25.0,
            scored_forecast_count=15,
            popularity_score=40,
            popularity_points=400,
        )
        UserProfile.objects.filter(user=self.outside).update(
            reputation_points=50,
            reputation_score=5.0,
            scored_forecast_count=11,
            popularity_score=10,
            popularity_points=100,
        )

    def test_only_relative_number_one_gets_badge(self):
        badges = get_user_platform_top_rank_badges(self.leader)
        self.assertEqual(len(badges), 1)
        self.assertEqual(badges[0]["kind"], REPUTATION_RELATIVE)
        self.assertEqual(badges[0]["rank"], 1)

    def test_absolute_leader_without_relative_first_gets_no_badge(self):
        badges = get_user_platform_top_rank_badges(self.second)
        self.assertEqual(badges, [])

    def test_relative_reputation_requires_qualification(self):
        unqualified = User.objects.create_user(username="newbie", password="pass")
        UserProfile.objects.filter(user=unqualified).update(
            reputation_points=999,
            reputation_score=99.0,
            scored_forecast_count=5,
        )
        badges = get_user_platform_top_rank_badges(unqualified)
        self.assertEqual(badges, [])

    def test_outside_top_one_gets_no_badges(self):
        badges = get_user_platform_top_rank_badges(self.outside)
        self.assertEqual(badges, [])

    def test_profile_renders_rank_badge_for_relative_leader(self):
        from django.urls import reverse

        response = self.client.get(
            reverse("accounts:profile", kwargs={"username": self.leader.username})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pr-profile-rank-badge")
        self.assertContains(response, "#1")

    def test_profile_hides_rank_badge_for_non_leader(self):
        from django.urls import reverse

        response = self.client.get(
            reverse("accounts:profile", kwargs={"username": self.outside.username})
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "pr-profile-rank-badge")

    def test_profile_rank_badge_renders_in_spanish(self):
        from django.urls import reverse

        response = self.client.get(
            reverse("accounts:profile", kwargs={"username": self.leader.username}),
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ranking relativo de la plataforma")

    def test_platform_rank_index_matches_direct_lookup(self):
        cache.clear()
        index = build_platform_top_rank_index()
        badges = get_user_platform_top_rank_badges(self.leader)
        self.assertEqual(badges, index.get(self.leader.pk, []))

    def test_forum_post_renders_rank_badge_for_relative_leader(self):
        from pulse.models import Post

        post = Post.objects.create(user=self.leader, body="hola")
        response = self.client.get("/forum/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pr-profile-rank-badge")
        self.assertContains(response, post.body)
