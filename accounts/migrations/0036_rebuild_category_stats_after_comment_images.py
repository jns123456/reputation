from django.db import migrations


def rebuild_category_stats(apps, schema_editor):
    from accounts.category_stats_services import rebuild_all_category_stats

    rebuild_all_category_stats()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0035_notification_dm_message_and_more"),
        ("comments", "0004_comment_image"),
    ]

    operations = [
        migrations.RunPython(rebuild_category_stats, migrations.RunPython.noop),
    ]
