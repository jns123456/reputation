"""Creator program and subscriber membership (no on-platform payments)."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from accounts.models import CreatorProgram, CreatorSubscription, SubscriberAudience


def get_or_create_creator_program(user):
    program, _created = CreatorProgram.objects.get_or_create(user=user)
    return program


def update_creator_program(*, user, is_enabled, tagline, welcome_message, monthly_price_cents):
    if monthly_price_cents < 0 or monthly_price_cents > 999_00:
        raise ValidationError(_("Monthly price must be between $0 and $999."))

    program = get_or_create_creator_program(user)
    program.is_enabled = is_enabled
    program.tagline = (tagline or "").strip()
    program.welcome_message = (welcome_message or "").strip()
    program.monthly_price_cents = monthly_price_cents
    program.save(
        update_fields=[
            "is_enabled",
            "tagline",
            "welcome_message",
            "monthly_price_cents",
            "updated_at",
        ]
    )
    return program


def subscribe_to_creator(*, subscriber, creator):
    from accounts.write_guard import guard_write_action

    if subscriber.pk == creator.pk:
        raise ValidationError(_("You cannot subscribe to yourself."))

    program = getattr(creator, "creator_program", None)
    if program is None or not program.is_enabled:
        raise ValidationError(_("This creator is not accepting subscribers yet."))

    guard_write_action(
        action="creator_subscribe",
        user=subscriber,
        content_scope="write:creator_subscribe",
    )

    with transaction.atomic():
        membership, created = CreatorSubscription.objects.get_or_create(
            creator=creator,
            subscriber=subscriber,
            defaults={"status": CreatorSubscription.Status.ACTIVE},
        )
        if not created and membership.status != CreatorSubscription.Status.ACTIVE:
            membership.status = CreatorSubscription.Status.ACTIVE
            membership.cancelled_at = None
            membership.save(update_fields=["status", "cancelled_at"])
    return membership


def unsubscribe_from_creator(*, subscriber, creator):
    membership = CreatorSubscription.objects.filter(
        creator=creator,
        subscriber=subscriber,
        status=CreatorSubscription.Status.ACTIVE,
    ).first()
    if membership is None:
        return None

    membership.status = CreatorSubscription.Status.CANCELLED
    membership.cancelled_at = timezone.now()
    membership.save(update_fields=["status", "cancelled_at"])
    return membership


def is_active_subscriber(*, viewer, creator) -> bool:
    if not viewer.is_authenticated:
        return False
    if viewer.pk == creator.pk:
        return True
    return CreatorSubscription.objects.filter(
        creator=creator,
        subscriber=viewer,
        status=CreatorSubscription.Status.ACTIVE,
    ).exists()


def can_view_audience_content(*, viewer, creator, audience: str) -> bool:
    if audience != SubscriberAudience.SUBSCRIBERS:
        return True
    if not getattr(creator, "creator_program", None) or not creator.creator_program.is_enabled:
        return True
    return is_active_subscriber(viewer=viewer, creator=creator)


def validate_creator_audience(*, user, audience: str):
    if audience == SubscriberAudience.SUBSCRIBERS:
        program = getattr(user, "creator_program", None)
        if program is None or not program.is_enabled:
            raise ValidationError(
                _("Enable your creator program before publishing subscriber-only content.")
            )


def count_active_subscribers(creator) -> int:
    return CreatorSubscription.objects.filter(
        creator=creator,
        status=CreatorSubscription.Status.ACTIVE,
    ).count()
