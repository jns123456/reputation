"""Backfill ``game_start_time`` for markets missing a scheduled start."""

from django.db import migrations
from django.db.models import F


def backfill_market_game_start_times(apps, schema_editor):
    Market = apps.get_model("markets", "Market")
    Market.objects.filter(
        game_start_time__isnull=True,
        close_date__isnull=False,
    ).update(game_start_time=F("close_date"))


class Migration(migrations.Migration):
    dependencies = [
        ("markets", "0018_backfill_f1_race_game_start_time"),
    ]

    operations = [
        migrations.RunPython(backfill_market_game_start_times, migrations.RunPython.noop),
    ]
