"""Bookmark toggle logic."""

from accounts.models import Bookmark


def toggle_bookmark(*, user, target_type, target_id):
    bookmark = Bookmark.objects.filter(
        user=user,
        target_type=target_type,
        target_id=target_id,
    ).first()
    if bookmark:
        bookmark.delete()
        return False
    Bookmark.objects.create(
        user=user,
        target_type=target_type,
        target_id=target_id,
    )
    return True
