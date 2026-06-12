from django.db import migrations


def backfill_profile_leaderboard_stats(apps, schema_editor):
    from accounts.profile_stats_services import rebuild_profile_reputation_counters

    rebuild_profile_reputation_counters()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0030_stackable_achievements"),
        ("reputation", "0007_reputationevent_unique_prediction_event_type"),
    ]

    operations = [
        migrations.RunPython(backfill_profile_leaderboard_stats, migrations.RunPython.noop),
    ]
