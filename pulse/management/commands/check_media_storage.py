from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from PIL import Image


class Command(BaseCommand):
    help = "Upload and delete a tiny test image to verify media storage (R2/S3)."

    def handle(self, *args, **options):
        if not getattr(settings, "USE_S3_MEDIA", False):
            self.stdout.write(
                self.style.WARNING(
                    "USE_S3_MEDIA is False — using local MEDIA_ROOT. "
                    "Set R2/S3 env vars for production storage."
                )
            )

        buffer = BytesIO()
        Image.new("RGB", (4, 4), color="green").save(buffer, format="PNG")
        key = "pulse/healthcheck/media-storage-test.png"

        try:
            if default_storage.exists(key):
                default_storage.delete(key)
            saved_name = default_storage.save(key, ContentFile(buffer.getvalue()))
            url = default_storage.url(saved_name)
            default_storage.delete(saved_name)
        except Exception as exc:
            raise CommandError(f"Media storage check failed: {exc}") from exc

        self.stdout.write(self.style.SUCCESS(f"Media storage OK — test URL was {url}"))
