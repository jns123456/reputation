from django.db import migrations, models


def backfill_browse_area_slugs(apps, schema_editor):
    Market = apps.get_model("markets", "Market")
    from markets.browse_areas import compute_browse_area_slugs

    batch = []
    for market in Market.objects.iterator(chunk_size=500):
        slugs = compute_browse_area_slugs(market)
        if market.browse_area_slugs != slugs:
            market.browse_area_slugs = slugs
            batch.append(market)
        if len(batch) >= 500:
            Market.objects.bulk_update(batch, ["browse_area_slugs"])
            batch.clear()
    if batch:
        Market.objects.bulk_update(batch, ["browse_area_slugs"])


class Migration(migrations.Migration):
    dependencies = [
        ("markets", "0010_market_spanish_copy"),
    ]

    operations = [
        migrations.AddField(
            model_name="market",
            name="browse_area_slugs",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(backfill_browse_area_slugs, migrations.RunPython.noop),
    ]
