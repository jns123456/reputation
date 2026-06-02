from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.deploy_checks import INSECURE_SECRET_KEY, validate_production_settings


class ValidateProductionSettingsTests(SimpleTestCase):
    def _strong_key(self):
        return "x" * 50

    def test_skips_when_debug(self):
        validate_production_settings(
            debug=True,
            secret_key=INSECURE_SECRET_KEY,
            email_verification_dev_show_link=True,
        )

    def test_skips_when_running_tests(self):
        validate_production_settings(
            debug=False,
            secret_key=INSECURE_SECRET_KEY,
            email_verification_dev_show_link=True,
            running_tests=True,
        )

    def test_rejects_insecure_default_secret_key(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            validate_production_settings(
                debug=False,
                secret_key=INSECURE_SECRET_KEY,
                email_verification_dev_show_link=False,
            )
        self.assertIn("SECRET_KEY", str(ctx.exception))

    def test_rejects_short_secret_key(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            validate_production_settings(
                debug=False,
                secret_key="too-short",
                email_verification_dev_show_link=False,
            )
        self.assertIn("SECRET_KEY", str(ctx.exception))

    def test_rejects_dev_verification_link_in_production(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            validate_production_settings(
                debug=False,
                secret_key=self._strong_key(),
                email_verification_dev_show_link=True,
            )
        self.assertIn("EMAIL_VERIFICATION_DEV_SHOW_LINK", str(ctx.exception))

    def test_passes_with_safe_production_settings(self):
        validate_production_settings(
            debug=False,
            secret_key=self._strong_key(),
            email_verification_dev_show_link=False,
        )
