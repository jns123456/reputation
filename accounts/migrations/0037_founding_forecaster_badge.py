"""Backfill founding forecaster badges for the first 100 signups."""

from django.db import migrations
from django.db.models import Q


FOUNDING_FORECASTER_LIMIT = 100
FOUNDING_FORECASTER_CODE = "founding_forecaster"


def _is_founding_forecaster(User, user):
    earlier_count = User.objects.filter(
        Q(created_at__lt=user.created_at)
        | Q(created_at=user.created_at, pk__lt=user.pk)
    ).count()
    return earlier_count < FOUNDING_FORECASTER_LIMIT


def backfill_founding_forecaster_badges(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    UserAchievement = apps.get_model("accounts", "UserAchievement")

    for user in User.objects.all().iterator():
        if not _is_founding_forecaster(User, user):
            continue
        if UserAchievement.objects.filter(user_id=user.id, code=FOUNDING_FORECASTER_CODE).exists():
            continue
        UserAchievement.objects.create(user_id=user.id, code=FOUNDING_FORECASTER_CODE)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0036_rebuild_category_stats_after_comment_images"),
    ]

    operations = [
        migrations.RunPython(
            backfill_founding_forecaster_badges,
            migrations.RunPython.noop,
        ),
    ]
