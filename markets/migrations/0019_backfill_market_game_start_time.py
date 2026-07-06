"""Backfill ``game_start_time`` for markets missing a scheduled start."""

from django.db import migrations


def backfill_market_game_start_times(apps, schema_editor):
    Market = apps.get_model("markets", "Market")
    to_update = []
    for market in Market.objects.filter(game_start_time__isnull=True, close_date__isnull=False):
        market.game_start_time = market.close_date
        to_update.append(market)
    if to_update:
        Market.objects.bulk_update(to_update, ["game_start_time"])


class Migration(migrations.Migration):
    dependencies = [
        ("markets", "0018_backfill_f1_race_game_start_time"),
    ]

    operations = [
        migrations.RunPython(backfill_market_game_start_times, migrations.RunPython.noop),
    ]
