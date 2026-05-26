from django.db import migrations

from markets.categories import FIFA_WORLD_CUP_CATEGORY_SLUG


def backfill_world_cup_category(apps, schema_editor):
    Market = apps.get_model("markets", "Market")
    Market.objects.filter(external_id__startswith="wc-match:").update(
        canonical_category_slug=FIFA_WORLD_CUP_CATEGORY_SLUG,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("markets", "0006_rename_markets_mar_status_8a1f2c_idx_markets_mar_status_9d704b_idx"),
    ]

    operations = [
        migrations.RunPython(backfill_world_cup_category, migrations.RunPython.noop),
    ]
