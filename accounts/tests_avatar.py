import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from PIL import Image

from accounts.forms import ProfileEditForm
from accounts.models import User


def _test_avatar(name="avatar.png", content_type="image/png"):
    buffer = BytesIO()
    Image.new("RGB", (8, 8), color="blue").save(buffer, format="PNG")
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type=content_type)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class AvatarUploadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="avataruser",
            password="pass",
            onboarding_completed=True,
        )
        self.client = Client()
        self.client.login(username="avataruser", password="pass")

    def test_avatar_upload_updates_profile_photo(self):
        response = self.client.post(
            "/accounts/profile/avatar/",
            {"avatar": _test_avatar()},
        )
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar)
        self.assertIn("avatars/", self.user.avatar.name)

    def test_avatar_upload_rejects_large_file(self):
        large = SimpleUploadedFile(
            "large.png",
            b"x" * (5 * 1024 * 1024 + 1),
            content_type="image/png",
        )
        response = self.client.post(
            "/accounts/profile/avatar/",
            {"avatar": large},
        )
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)

    def test_profile_edit_form_saves_avatar(self):
        form = ProfileEditForm(
            data={
                "email": self.user.email,
                "display_name": "",
                "identity_mode": User.IdentityMode.PUBLIC,
                "bio": "",
            },
            files={"avatar": _test_avatar()},
            instance=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNotNone(form.cleaned_data.get("avatar"))
        form.save()
        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar)

    def test_profile_edit_can_upload_avatar(self):
        response = self.client.post(
            "/accounts/profile/edit/",
            {
                "email": self.user.email,
                "display_name": "",
                "identity_mode": User.IdentityMode.PUBLIC,
                "bio": "",
                "avatar": _test_avatar(),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar)

    def test_profile_page_shows_change_photo_control_for_owner(self):
        response = self.client.get("/accounts/users/avataruser/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Change profile photo")

    def test_profile_page_hides_change_photo_control_for_other_users(self):
        other = User.objects.create_user(
            username="viewer",
            password="pass",
            onboarding_completed=True,
        )
        self.client.login(username="viewer", password="pass")
        response = self.client.get("/accounts/users/avataruser/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Change profile photo")
