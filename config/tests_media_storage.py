from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.media_storage import is_r2_endpoint, resolve_s3_media_settings


class MediaStorageSettingsTests(SimpleTestCase):
    def test_is_r2_endpoint(self):
        self.assertTrue(
            is_r2_endpoint("https://abc123.r2.cloudflarestorage.com")
        )
        self.assertFalse(is_r2_endpoint("https://s3.us-east-1.amazonaws.com"))

    def test_aws_s3_defaults(self):
        settings = resolve_s3_media_settings(bucket_name="predictstamp-media")
        self.assertEqual(
            settings["AWS_S3_CUSTOM_DOMAIN"],
            "predictstamp-media.s3.us-east-1.amazonaws.com",
        )
        self.assertEqual(settings["AWS_DEFAULT_ACL"], "public-read")
        self.assertNotIn("AWS_S3_ENDPOINT_URL", settings)

    def test_r2_requires_public_domain(self):
        with self.assertRaises(ImproperlyConfigured):
            resolve_s3_media_settings(
                bucket_name="predictstamp-media",
                endpoint_url="https://abc123.r2.cloudflarestorage.com",
            )

    def test_r2_settings(self):
        settings = resolve_s3_media_settings(
            bucket_name="predictstamp-media",
            endpoint_url="https://abc123.r2.cloudflarestorage.com",
            custom_domain="pub-abc123.r2.dev",
            running_tests=False,
        )
        self.assertEqual(settings["AWS_S3_ENDPOINT_URL"], "https://abc123.r2.cloudflarestorage.com")
        self.assertEqual(settings["AWS_S3_REGION_NAME"], "auto")
        self.assertEqual(settings["AWS_S3_CUSTOM_DOMAIN"], "pub-abc123.r2.dev")
        self.assertIsNone(settings["AWS_DEFAULT_ACL"])
        self.assertEqual(settings["MEDIA_URL"], "https://pub-abc123.r2.dev/")
