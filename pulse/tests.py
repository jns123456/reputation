from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from PIL import Image

from accounts.models import Bookmark, User
from pulse.models import Post
from pulse.services import create_post


def _test_image(name="test.png"):
    buffer = BytesIO()
    Image.new("RGB", (8, 8), color="red").save(buffer, format="PNG")
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type="image/png")


class ForumPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="forumuser", password="pass")
        self.other = User.objects.create_user(username="other", password="pass")
        self.post = create_post(user=self.other, body="Hello Forum!")
        self.client = Client()

    def test_forum_page_lists_posts(self):
        response = self.client.get("/forum/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Forum")
        self.assertContains(response, "Hello Forum!")

    def test_create_post_requires_login(self):
        response = self.client.post("/forum/create/", {"body": "Nope"})
        self.assertEqual(response.status_code, 302)

    def test_create_post_with_text(self):
        self.client.login(username="forumuser", password="pass")
        response = self.client.post(
            "/forum/create/",
            {"body": "My first post"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My first post")
        self.assertTrue(Post.objects.filter(user=self.user, body="My first post").exists())

    def test_create_post_with_image(self):
        self.client.login(username="forumuser", password="pass")
        response = self.client.post(
            "/forum/create/",
            {"body": "Photo post", "image": _test_image()},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        post = Post.objects.get(user=self.user, body="Photo post")
        self.assertTrue(post.image)

    def test_create_post_requires_body_or_image(self):
        self.client.login(username="forumuser", password="pass")
        response = self.client.post(
            "/forum/create/",
            {},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 400)

    def test_create_post_with_poll(self):
        self.client.login(username="forumuser", password="pass")
        response = self.client.post(
            "/forum/create/",
            {
                "body": "Which team wins?",
                "enable_poll": "1",
                "poll_option_0": "Team A",
                "poll_option_1": "Team B",
                "poll_days": "3",
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        post = Post.objects.get(user=self.user, body="Which team wins?")
        self.assertTrue(hasattr(post, "poll"))
        self.assertEqual(post.poll.options.count(), 2)

    def test_poll_vote(self):
        from pulse.models import Poll

        author = User.objects.create_user(username="author", password="pass")
        post = create_post(
            user=author,
            body="Pick one",
            poll_payload={"options": ["Red", "Blue"], "duration_days": 1},
        )
        poll = Poll.objects.get(post=post)
        option = poll.options.first()
        self.client.login(username="forumuser", password="pass")
        response = self.client.post(
            f"/forum/{post.id}/poll/vote/",
            {"option_id": option.id},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Red")
        self.assertContains(response, "%")

    def test_poll_vote_blocks_author(self):
        from pulse.models import Poll

        post = create_post(
            user=self.user,
            body="My poll",
            poll_payload={"options": ["Yes", "No"], "duration_days": 1},
        )
        poll = Poll.objects.get(post=post)
        option = poll.options.first()
        self.client.login(username="forumuser", password="pass")
        response = self.client.post(
            f"/forum/{post.id}/poll/vote/",
            {"option_id": option.id},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 400)

    def test_vote_on_forum_post(self):
        self.client.login(username="forumuser", password="pass")
        response = self.client.post(
            "/comments/vote/",
            {
                "target_type": "pulse_post",
                "target_id": self.post.id,
                "value": "1",
                "layout": "forum",
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "is-active")
        self.post.refresh_from_db()
        self.assertEqual(self.post.popularity_score, 1)

    def test_bookmark_forum_post(self):
        self.client.login(username="forumuser", password="pass")
        response = self.client.post(
            "/accounts/bookmarks/toggle/",
            {
                "target_type": Bookmark.TargetType.PULSE_POST,
                "target_id": self.post.id,
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Bookmark.objects.filter(
                user=self.user,
                target_type=Bookmark.TargetType.PULSE_POST,
                target_id=self.post.id,
            ).exists()
        )

    def test_comment_on_forum_post(self):
        self.client.login(username="forumuser", password="pass")
        response = self.client.post(
            f"/forum/{self.post.id}/comment/",
            {"body": "Great post!"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Great post!")

    def test_post_detail_page(self):
        response = self.client.get(f"/forum/{self.post.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hello Forum!")

    def test_repost_toggle(self):
        self.client.login(username="forumuser", password="pass")
        response = self.client.post(
            f"/forum/{self.post.id}/repost/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "is-active")
        self.assertTrue(
            Post.objects.filter(user=self.user, reposted_from=self.post).exists()
        )
        self.post.refresh_from_db()
        self.assertEqual(self.post.popularity_score, 1)

        response = self.client.post(
            f"/forum/{self.post.id}/repost/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "is-active")
        self.assertFalse(
            Post.objects.filter(user=self.user, reposted_from=self.post).exists()
        )
        self.post.refresh_from_db()
        self.assertEqual(self.post.popularity_score, 0)

    def test_cannot_repost_own_post(self):
        self.client.login(username="other", password="pass")
        response = self.client.post(f"/forum/{self.post.id}/repost/")
        self.assertEqual(response.status_code, 400)

    def test_delete_own_post(self):
        own_post = create_post(user=self.user, body="Delete me")
        self.client.login(username="forumuser", password="pass")
        response = self.client.post(
            f"/forum/{own_post.id}/delete/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Post.objects.filter(pk=own_post.id).exists())

    def test_cannot_delete_other_users_post(self):
        self.client.login(username="forumuser", password="pass")
        response = self.client.post(f"/forum/{self.post.id}/delete/")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Post.objects.filter(pk=self.post.id).exists())

    def test_post_more_menu_on_feed(self):
        response = self.client.get("/forum/")
        self.assertContains(response, "x-tweet-menu")
        self.assertContains(response, "Copy link")
