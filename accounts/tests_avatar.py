from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.avatar_services import avatar_seed, generated_avatar_url

User = get_user_model()


@override_settings(EMAIL_VERIFICATION_REQUIRED=False)
class GeneratedAvatarTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="avataruser",
            email="avatar@example.com",
            password="pass",
            display_name="Avatar User",
            email_verified_at=timezone.now(),
            onboarding_completed=True,
        )

    def test_seed_uses_primary_key(self):
        self.assertEqual(avatar_seed(self.user), str(self.user.pk))

    def test_generated_url_is_stable(self):
        self.assertEqual(
            generated_avatar_url(self.user),
            generated_avatar_url(self.user),
        )

    @override_settings(
        AVATAR_DICEBEAR_BASE_URL="https://api.dicebear.com/9.x",
        AVATAR_DICEBEAR_STYLE="identicon",
    )
    def test_generated_url_contains_seed_and_style(self):
        url = generated_avatar_url(self.user, size=128)
        self.assertIn("identicon/png", url)
        self.assertIn(f"seed={self.user.pk}", url)
        self.assertIn("size=128", url)

    def test_profile_page_renders_generated_avatar(self):
        self.client.login(username="avataruser", password="pass")
        response = self.client.get("/accounts/users/avataruser/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn(f"seed={self.user.pk}", html)
        self.assertIn("api.dicebear.com", html)

    def test_avatar_upload_endpoint_removed(self):
        response = self.client.post("/accounts/profile/avatar/")
        self.assertEqual(response.status_code, 404)
