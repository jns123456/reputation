"""Shared upload validation for user-facing images (forum, DMs, etc.)."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}

ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}


def max_upload_image_bytes():
    return getattr(settings, "PULSE_MAX_IMAGE_BYTES", 5 * 1024 * 1024)


def clean_uploaded_image(image):
    """Validate an optional uploaded image; return ``None`` when absent."""
    if not image:
        return None

    max_bytes = max_upload_image_bytes()
    if image.size > max_bytes:
        raise ValidationError(_("Image must be 5 MB or smaller."))

    content_type = getattr(image, "content_type", "")
    if content_type and content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise ValidationError(_("Upload a JPEG, PNG, WebP, or GIF image."))

    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(image) as probe:
            probe.verify()
            detected = (probe.format or "").upper()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError(_("Upload a JPEG, PNG, WebP, or GIF image.")) from exc
    finally:
        image.seek(0)

    if detected not in ALLOWED_IMAGE_FORMATS:
        raise ValidationError(_("Upload a JPEG, PNG, WebP, or GIF image."))

    return image
