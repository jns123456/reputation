"""Bookmark read queries."""

from accounts.models import Bookmark


def get_user_bookmarked_ids(user, target_type, target_ids):
    if not user.is_authenticated or not target_ids:
        return set()

    return set(
        Bookmark.objects.filter(
            user=user,
            target_type=target_type,
            target_id__in=target_ids,
        ).values_list("target_id", flat=True)
    )


def is_bookmarked(user, target_type, target_id):
    if not user.is_authenticated:
        return False
    return Bookmark.objects.filter(
        user=user,
        target_type=target_type,
        target_id=target_id,
    ).exists()
