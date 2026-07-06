"""Backfill ``game_start_time`` for F1 Grand Prix markets imported before kickoff gating."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("markets", "0017_backfill_esports_category"),
    ]

    operations = [
        # F1 rows are covered by the universal SQL backfill in 0019. This
        # migration previously used a Python loop over all markets and OOM'd on
        # Heroku release (large ``polymarket_*_raw`` JSON payloads).
        migrations.RunPython(migrations.RunPython.noop, migrations.RunPython.noop),
    ]
