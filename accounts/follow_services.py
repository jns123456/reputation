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

    from accounts.write_guard import guard_write_action

    guard_write_action(action="follow", user=follower)

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


def toggle_topic_follow(*, user, category_slug):
    """Follow/unfollow a canonical category. Returns True when now following."""
    from markets.categories import get_category_for_slug

    if get_category_for_slug(category_slug) is None:
        raise ValidationError(_("Unknown topic."))

    from accounts.models import TopicFollow

    existing = TopicFollow.objects.filter(user=user, category_slug=category_slug).first()
    if existing:
        existing.delete()
        _clear_affinity(user)
        return False

    from accounts.write_guard import guard_write_action

    guard_write_action(action="follow", user=user)
    TopicFollow.objects.create(user=user, category_slug=category_slug)
    _clear_affinity(user)
    return True


def toggle_market_watch(*, user, market):
    """Watch/unwatch a market. Returns True when now watching."""
    from accounts.models import MarketWatch

    existing = MarketWatch.objects.filter(user=user, market=market).first()
    if existing:
        existing.delete()
        return False

    from accounts.write_guard import guard_write_action

    guard_write_action(action="follow", user=user)
    MarketWatch.objects.create(user=user, market=market)
    return True


def _clear_affinity(user):
    try:
        from dashboard.personalization import clear_user_affinity_cache

        clear_user_affinity_cache(user)
    except Exception:
        logger.exception("Failed clearing affinity cache for user=%s", user.pk)


def ensure_mutual_follows_among_active_users(*, dry_run=False):
    """Create missing follow edges so every active user follows every other active user."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user_ids = list(User.objects.filter(is_active=True).values_list("id", flat=True))
    if len(user_ids) < 2:
        return {
            "users": len(user_ids),
            "created": 0,
            "existing": 0,
            "expected": 0,
        }

    user_id_set = set(user_ids)
    existing = set(
        UserFollow.objects.filter(
            follower_id__in=user_id_set,
            following_id__in=user_id_set,
        ).values_list("follower_id", "following_id")
    )

    to_create = [
        UserFollow(follower_id=follower_id, following_id=following_id)
        for follower_id in user_ids
        for following_id in user_ids
        if follower_id != following_id and (follower_id, following_id) not in existing
    ]
    expected = len(user_ids) * (len(user_ids) - 1)

    if not dry_run and to_create:
        UserFollow.objects.bulk_create(to_create, ignore_conflicts=True)

    return {
        "users": len(user_ids),
        "created": len(to_create),
        "existing": len(existing),
        "expected": expected,
    }
