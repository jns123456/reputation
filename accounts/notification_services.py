"""Notification creation and management."""

from django.utils import timezone

from accounts.models import Notification, NotificationPreference, UserFollow

LOGIN_NOTIFICATION_TOAST_SESSION_KEY = "show_notification_toast"


def get_or_create_notification_preferences(user):
    preferences, _ = NotificationPreference.objects.get_or_create(user=user)
    return preferences


def _should_notify_in_app(*, user_id):
    preferences = NotificationPreference.objects.filter(user_id=user_id).first()
    if preferences is None:
        return True
    return preferences.notify_in_app


def _create_notification(*, recipient, **fields):
    if not _should_notify_in_app(user_id=recipient.id):
        return None
    notification = Notification.objects.create(recipient=recipient, **fields)
    from accounts.nav_cache import invalidate_notification_nav_cache

    invalidate_notification_nav_cache(recipient.id)
    return notification


def notify_followers_of_prediction(*, prediction):
    """Create in-app notifications for followers when a user publishes a forecast."""
    actor = prediction.user
    follower_ids = list(
        UserFollow.objects.filter(following=actor).values_list("follower_id", flat=True)
    )
    if not follower_ids:
        return []

    preferences_by_user = {
        pref.user_id: pref
        for pref in NotificationPreference.objects.filter(user_id__in=follower_ids)
    }

    created = []
    for follower_id in follower_ids:
        preferences = preferences_by_user.get(follower_id)
        if preferences is None:
            preferences = NotificationPreference.objects.create(user_id=follower_id)
            preferences_by_user[follower_id] = preferences

        if not preferences.notify_followed_predictions:
            continue
        if not _should_notify_in_app(user_id=follower_id):
            continue

        notification, was_created = Notification.objects.get_or_create(
            recipient_id=follower_id,
            notification_type=Notification.NotificationType.FOLLOWED_USER_PREDICTION,
            prediction=prediction,
            defaults={"actor": actor},
        )
        if was_created:
            created.append(notification)
            from accounts.nav_cache import invalidate_notification_nav_cache

            invalidate_notification_nav_cache(follower_id)

    return created


def notify_new_follower(*, follow):
    """Notify a user when someone follows them."""
    recipient = follow.following
    actor = follow.follower

    preferences = get_or_create_notification_preferences(recipient)
    if not preferences.notify_new_follower:
        return None
    if not _should_notify_in_app(user_id=recipient.id):
        return None

    notification = Notification.objects.create(
        recipient=recipient,
        actor=actor,
        notification_type=Notification.NotificationType.NEW_FOLLOWER,
        user_follow=follow,
    )
    from accounts.nav_cache import invalidate_notification_nav_cache

    invalidate_notification_nav_cache(recipient.id)
    return notification


def notify_vote_received(*, actor, recipient, target, target_type, value):
    """Notify content owner when someone upvotes or downvotes their content."""
    if recipient.id == actor.id:
        return None

    preferences = get_or_create_notification_preferences(recipient)
    if not preferences.notify_votes_received:
        return None
    if not _should_notify_in_app(user_id=recipient.id):
        return None

    if value == 1:
        notification_type = Notification.NotificationType.UPVOTE_RECEIVED
    elif value == -1:
        notification_type = Notification.NotificationType.DOWNVOTE_RECEIVED
    else:
        return None

    if target_type == "prediction":
        opposite_type = (
            Notification.NotificationType.DOWNVOTE_RECEIVED
            if notification_type == Notification.NotificationType.UPVOTE_RECEIVED
            else Notification.NotificationType.UPVOTE_RECEIVED
        )
        Notification.objects.filter(
            recipient=recipient,
            prediction=target,
            notification_type=opposite_type,
            actor=actor,
        ).delete()
        notification, _ = Notification.objects.update_or_create(
            recipient=recipient,
            notification_type=notification_type,
            prediction=target,
            defaults={
                "actor": actor,
                "vote_target_type": target_type,
                "vote_target_id": target.id,
            },
        )
        return notification

    kwargs = {
        "actor": actor,
        "notification_type": notification_type,
        "vote_target_type": target_type,
        "vote_target_id": target.id,
    }

    if target_type == "comment":
        kwargs["comment"] = target

    return _create_notification(recipient=recipient, **kwargs)


def notify_prediction_resolved(*, prediction, reputation_event):
    """Notify a user when their forecast is resolved and reputation is applied."""
    recipient = prediction.user

    preferences = get_or_create_notification_preferences(recipient)
    if not preferences.notify_prediction_resolved:
        return None
    if not _should_notify_in_app(user_id=recipient.id):
        return None

    notification, _ = Notification.objects.get_or_create(
        recipient=recipient,
        notification_type=Notification.NotificationType.PREDICTION_RESOLVED,
        prediction=prediction,
        defaults={
            "actor": recipient,
            "reputation_event": reputation_event,
        },
    )
    return notification


def notify_comment_reply(*, comment=None, pulse_comment=None):
    """Notify the parent author when their comment receives a reply.

    Pass a market ``comment`` or a forum ``pulse_comment`` (exactly one). The
    reply object itself is linked so the notification deep-links to it.
    """
    reply = comment if comment is not None else pulse_comment
    parent = getattr(reply, "parent_comment", None)
    if parent is None:
        return None

    recipient = parent.user
    actor = reply.user
    if recipient.id == actor.id:
        return None

    preferences = get_or_create_notification_preferences(recipient)
    if not preferences.notify_replies:
        return None

    fields = {
        "actor": actor,
        "notification_type": Notification.NotificationType.COMMENT_REPLY,
    }
    if comment is not None:
        fields["comment"] = comment
    else:
        fields["pulse_comment"] = pulse_comment
    return _create_notification(recipient=recipient, **fields)


def notify_mentions(
    *,
    actor,
    body,
    comment=None,
    pulse_comment=None,
    pulse_post=None,
    exclude_user_ids=(),
):
    """Create MENTION notifications for every @username found in ``body``."""
    from accounts.mention_services import extract_mention_usernames
    from accounts.models import User

    usernames = extract_mention_usernames(body)
    if not usernames:
        return []

    exclude_ids = set(exclude_user_ids) | {actor.id}
    recipients = User.objects.filter(username__in=usernames).exclude(id__in=exclude_ids)

    created = []
    for recipient in recipients:
        preferences = get_or_create_notification_preferences(recipient)
        if not preferences.notify_mentions:
            continue
        notification = _create_notification(
            recipient=recipient,
            actor=actor,
            notification_type=Notification.NotificationType.MENTION,
            comment=comment,
            pulse_comment=pulse_comment,
            pulse_post=pulse_post,
        )
        if notification:
            created.append(notification)
    return created


def notify_market_resolving(*, market):
    """Remind users with an open forecast that ``market`` is about to close.

    Idempotent per (recipient, market): a unique constraint prevents duplicate
    reminders if the beat task runs more than once before the market closes.
    Respects each user's ``notify_market_resolving`` preference. The reminder is
    a popularity-neutral nudge — it never touches reputation (AGENTS.md §6).
    """
    from predictions.models import Prediction

    recipient_ids = list(
        Prediction.objects.filter(
            market=market,
            status=Prediction.Status.PENDING,
        )
        .values_list("user_id", flat=True)
        .distinct()
    )
    if not recipient_ids:
        return []

    preferences_by_user = {
        pref.user_id: pref
        for pref in NotificationPreference.objects.filter(user_id__in=recipient_ids)
    }

    created = []
    for recipient_id in recipient_ids:
        preferences = preferences_by_user.get(recipient_id)
        if preferences is None:
            preferences = NotificationPreference.objects.create(user_id=recipient_id)
            preferences_by_user[recipient_id] = preferences
        if not preferences.notify_market_resolving:
            continue
        if not _should_notify_in_app(user_id=recipient_id):
            continue

        notification, was_created = Notification.objects.get_or_create(
            recipient_id=recipient_id,
            notification_type=Notification.NotificationType.MARKET_RESOLVING,
            market=market,
            defaults={"actor_id": recipient_id},
        )
        if was_created:
            created.append(notification)
            from accounts.nav_cache import invalidate_notification_nav_cache

            invalidate_notification_nav_cache(recipient_id)

    return created


def mark_notification_read(*, notification, user):
    if notification.recipient_id != user.id:
        raise PermissionError("Cannot mark another user's notification as read.")
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
        from accounts.nav_cache import invalidate_notification_nav_cache

        invalidate_notification_nav_cache(user.id)


def mark_all_notifications_read(*, user):
    updated = Notification.objects.filter(recipient=user, read_at__isnull=True).update(
        read_at=timezone.now()
    )
    if updated:
        from accounts.nav_cache import invalidate_notification_nav_cache

        invalidate_notification_nav_cache(user.id)


def get_unread_notification_count(*, user):
    if not user or not user.is_authenticated:
        return 0
    return Notification.objects.filter(recipient=user, read_at__isnull=True).count()


def queue_login_notification_toast(*, request):
    """Flag the next authenticated page load to show unread notification alerts."""
    if not request.user.is_authenticated:
        return
    if get_unread_notification_count(user=request.user) > 0:
        request.session[LOGIN_NOTIFICATION_TOAST_SESSION_KEY] = True


def consume_login_notification_toast(*, request):
    """Return unread notifications for a one-time post-login toast, if queued."""
    if not request.user.is_authenticated:
        return None
    if not request.session.pop(LOGIN_NOTIFICATION_TOAST_SESSION_KEY, False):
        return None

    from accounts.notification_selectors import get_unread_recent_notifications

    notifications = list(get_unread_recent_notifications(user=request.user, limit=3))
    if not notifications:
        return None

    unread_count = get_unread_notification_count(user=request.user)
    return {
        "count": unread_count,
        "notifications": notifications,
    }
