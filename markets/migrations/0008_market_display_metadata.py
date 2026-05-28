from django.db import migrations, models


def backfill_market_display_metadata(apps, schema_editor):
    Market = apps.get_model("markets", "Market")
    from markets.display_metadata import (
        extract_card_image_url_from_market,
        extract_volume_total_from_market,
    )

    for market in Market.objects.iterator(chunk_size=200):
        market.volume_total = extract_volume_total_from_market(market)
        market.card_image_url = extract_card_image_url_from_market(market)
        market.save(update_fields=["volume_total", "card_image_url", "updated_at"])


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
