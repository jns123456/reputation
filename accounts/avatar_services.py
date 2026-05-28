from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

ALLOWED_AVATAR_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}


def validate_avatar_file(*, avatar):
    if not avatar:
        return

    max_bytes = getattr(settings, "AVATAR_MAX_IMAGE_BYTES", 5 * 1024 * 1024)
    if avatar.size > max_bytes:
        raise ValidationError(_("Profile photo must be 5 MB or smaller."))

    content_type = getattr(avatar, "content_type", "")
    if content_type and content_type not in ALLOWED_AVATAR_CONTENT_TYPES:
        raise ValidationError(_("Upload a JPEG, PNG, WebP, or GIF image."))


def update_user_avatar(*, user, avatar):
    """Replace the user's profile photo, deleting the previous file if present."""
    validate_avatar_file(avatar=avatar)

    if user.avatar:
        user.avatar.delete(save=False)

    user.avatar = avatar
    user.save(update_fields=["avatar", "updated_at"])
    return user
