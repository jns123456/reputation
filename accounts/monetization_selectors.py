"""Read queries for creator monetization."""

from accounts.models import CreatorProgram, CreatorSubscription


def get_creator_program(user):
    return CreatorProgram.objects.filter(user=user).first()


def get_creator_program_or_none(user):
    try:
        return user.creator_program
    except CreatorProgram.DoesNotExist:
        return None


def get_active_subscribers(creator, *, limit=100):
    return (
        CreatorSubscription.objects.filter(
            creator=creator,
            status=CreatorSubscription.Status.ACTIVE,
        )
        .select_related("subscriber", "subscriber__profile")
        .order_by("-started_at")[:limit]
    )


def get_subscriber_ids_for_creator(creator):
    return set(
        CreatorSubscription.objects.filter(
            creator=creator,
            status=CreatorSubscription.Status.ACTIVE,
        ).values_list("subscriber_id", flat=True)
    )


def is_viewer_subscribed(viewer, creator) -> bool:
    from accounts.monetization_services import is_active_subscriber

    return is_active_subscriber(viewer=viewer, creator=creator)
