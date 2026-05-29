"""User follow toggle logic."""

import logging

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from accounts.models import UserFollow

logger = logging.getLogger(__name__)


def toggle_follow(*, follower, following_user):
    if follower.id == following_user.id:
        raise ValidationError(_("Users cannot follow themselves."))

    follow = UserFollow.objects.filter(
        follower=follower,
        following=following_user,
    ).first()
    if follow:
        follow.delete()
        return False
    follow = UserFollow.objects.create(follower=follower, following=following_user)
    try:
        from accounts.notification_services import notify_new_follower

        notify_new_follower(follow=follow)
    except Exception:
        logger.exception(
            "Follow created but new-follower notification failed follower=%s following=%s",
            follower.pk,
            following_user.pk,
        )
    return True
