from django.db import migrations


def backfill_world_cup_browse_area_slugs(apps, schema_editor):
    from markets.browse_areas import compute_browse_area_slugs

    Market = apps.get_model("markets", "Market")
    batch = []
    qs = Market.objects.filter(external_id__startswith="wc-match:")
    for market in qs.iterator(chunk_size=500):
        slugs = compute_browse_area_slugs(market)
        if market.browse_area_slugs != slugs:
            market.browse_area_slugs = slugs
            batch.append(market)
        if len(batch) >= 500:
            Market.objects.bulk_update(batch, ["browse_area_slugs"])
            batch = []
    if batch:
        Market.objects.bulk_update(batch, ["browse_area_slugs"])


class Migration(migrations.Migration):
    dependencies = [
        ("markets", "0013_remove_kalshi_fields"),
    ]

    operations = [
        migrations.RunPython(
            backfill_world_cup_browse_area_slugs,
            migrations.RunPython.noop,
        ),
    ]
