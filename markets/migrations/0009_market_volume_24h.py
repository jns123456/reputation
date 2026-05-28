from django.db import migrations, models


def backfill_market_volume_24h(apps, schema_editor):
    Market = apps.get_model("markets", "Market")
    from markets.display_metadata import sync_market_display_metadata

    for market in Market.objects.iterator(chunk_size=200):
        sync_market_display_metadata(market, save=True)


class Migration(migrations.Migration):
    dependencies = [
        ("markets", "0008_market_display_metadata"),
    ]

    operations = [
        migrations.AddField(
            model_name="market",
            name="volume_24h",
            field=models.FloatField(db_index=True, default=0.0),
        ),
        migrations.RunPython(backfill_market_volume_24h, migrations.RunPython.noop),
    ]
