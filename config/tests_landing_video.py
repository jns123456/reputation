from django.test import TestCase

from config.landing_video import landing_video_path


class LandingHeroVideoViewTests(TestCase):
    def test_full_file_response(self):
        if not landing_video_path().is_file():
            self.skipTest("landing-hero.mp4 not present")

        response = self.client.get("/assets/landing-hero.mp4")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "video/mp4")
        self.assertEqual(response["Accept-Ranges"], "bytes")
        self.assertGreater(int(response["Content-Length"]), 0)

    def test_range_request_for_ios_safari(self):
        if not landing_video_path().is_file():
            self.skipTest("landing-hero.mp4 not present")

        response = self.client.get(
            "/assets/landing-hero.mp4",
            HTTP_RANGE="bytes=0-99",
        )

        self.assertEqual(response.status_code, 206)
        self.assertEqual(len(response.content), 100)
        self.assertTrue(response["Content-Range"].startswith("bytes 0-99/"))
        self.assertEqual(response["Content-Type"], "video/mp4")
