from django.test import TestCase

from config.brand_views import auth0_logo_path


class Auth0LogoViewTests(TestCase):
    def test_serves_logo(self):
        if not auth0_logo_path().is_file():
            self.skipTest("predictstamp-auth0-logo.jpg not present")

        response = self.client.get("/brand/auth0-logo.jpg")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/jpeg")
        body = b"".join(response.streaming_content)
        self.assertGreater(len(body), 0)
        self.assertEqual(response["Cache-Control"], "public, max-age=86400")
