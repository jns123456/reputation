from django.db import migrations


def backfill_category_leaderboard_stats(apps, schema_editor):
    from accounts.category_stats_services import rebuild_all_category_stats

    rebuild_all_category_stats()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0031_backfill_exit_correct_counts"),
        ("markets", "0015_market_liquidity_total"),
        ("predictions", "0006_prediction_audience"),
    ]

    operations = [
        migrations.RunPython(backfill_category_leaderboard_stats, migrations.RunPython.noop),
    ]
