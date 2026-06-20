from django.core.cache import cache
from django.test import TestCase

from accounts.models import User, UserProfile
from reputation.platform_rank import (
    POPULARITY,
    REPUTATION_ABSOLUTE,
    REPUTATION_RELATIVE,
    build_platform_top_rank_index,
    get_user_platform_top_rank_badges,
)


class PlatformRankBadgeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.first = User.objects.create_user(username="first", password="pass")
        self.second = User.objects.create_user(username="second", password="pass")
        self.third = User.objects.create_user(username="third", password="pass")
        self.outside = User.objects.create_user(username="outside", password="pass")

        UserProfile.objects.filter(user=self.first).update(
            reputation_points=300,
            reputation_score=25.0,
            scored_forecast_count=15,
            popularity_score=50,
            popularity_points=500,
        )
        UserProfile.objects.filter(user=self.second).update(
            reputation_points=200,
            reputation_score=40.0,
            scored_forecast_count=12,
            popularity_score=40,
            popularity_points=400,
        )
        UserProfile.objects.filter(user=self.third).update(
            reputation_points=100,
            reputation_score=10.0,
            scored_forecast_count=11,
            popularity_score=30,
            popularity_points=300,
        )
        UserProfile.objects.filter(user=self.outside).update(
            reputation_points=50,
            reputation_score=5.0,
            scored_forecast_count=11,
            popularity_score=10,
            popularity_points=100,
        )

    def test_top_three_absolute_reputation_gets_badge(self):
        badges = get_user_platform_top_rank_badges(self.first)
        kinds = {badge["kind"] for badge in badges}
        self.assertIn(REPUTATION_ABSOLUTE, kinds)
        self.assertEqual(
            next(badge for badge in badges if badge["kind"] == REPUTATION_ABSOLUTE)["rank"],
            1,
        )

    def test_relative_reputation_requires_qualification(self):
        unqualified = User.objects.create_user(username="newbie", password="pass")
        UserProfile.objects.filter(user=unqualified).update(
            reputation_points=999,
            reputation_score=99.0,
            scored_forecast_count=5,
        )
        badges = get_user_platform_top_rank_badges(unqualified)
        self.assertFalse(any(badge["kind"] == REPUTATION_RELATIVE for badge in badges))

    def test_relative_reputation_top_three_gets_badge(self):
        badges = get_user_platform_top_rank_badges(self.second)
        relative = next(badge for badge in badges if badge["kind"] == REPUTATION_RELATIVE)
        self.assertEqual(relative["rank"], 1)

    def test_outside_top_three_gets_no_badges(self):
        badges = get_user_platform_top_rank_badges(self.outside)
        self.assertEqual(badges, [])

    def test_popularity_top_three_gets_badge(self):
        badges = get_user_platform_top_rank_badges(self.third)
        popularity = next(badge for badge in badges if badge["kind"] == POPULARITY)
        self.assertEqual(popularity["rank"], 3)

    def test_profile_renders_rank_badge_for_top_user(self):
        from django.urls import reverse

        response = self.client.get(
            reverse("accounts:profile", kwargs={"username": self.first.username})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pr-profile-rank-badge")
        self.assertContains(response, "#1")

    def test_profile_hides_rank_badge_for_non_top_user(self):
        from django.urls import reverse

        response = self.client.get(
            reverse("accounts:profile", kwargs={"username": self.outside.username})
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "pr-profile-rank-badge")

    def test_profile_rank_badge_renders_in_spanish(self):
        from django.urls import reverse

        response = self.client.get(
            reverse("accounts:profile", kwargs={"username": self.first.username}),
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ranking absoluto de la plataforma")

    def test_platform_rank_index_matches_direct_lookup(self):
        cache.clear()
        index = build_platform_top_rank_index()
        badges = get_user_platform_top_rank_badges(self.first)
        self.assertEqual(badges, index.get(self.first.pk, []))

    def test_forum_post_renders_rank_badge_for_top_user(self):
        from pulse.models import Post

        post = Post.objects.create(user=self.first, body="hola")
        response = self.client.get("/forum/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pr-profile-rank-badge")
        self.assertContains(response, post.body)
