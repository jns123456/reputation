from django.db import migrations, models


def backfill_market_display_metadata(apps, schema_editor):
    Market = apps.get_model("markets", "Market")
    from markets.display_metadata import sync_market_display_metadata

    for market in Market.objects.iterator(chunk_size=200):
        sync_market_display_metadata(market, save=True)


class Migration(migrations.Migration):
    dependencies = [
        ("markets", "0007_backfill_world_cup_category"),
    ]

    operations = [
        migrations.AddField(
            model_name="market",
            name="volume_total",
            field=models.FloatField(db_index=True, default=0.0),
        ),
        migrations.AddField(
            model_name="market",
            name="card_image_url",
            field=models.URLField(blank=True, max_length=500),
        ),
        migrations.RunPython(backfill_market_display_metadata, migrations.RunPython.noop),
    ]
