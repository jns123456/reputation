from django.db import migrations


def backfill_formula1_browse_area_slugs(apps, schema_editor):
    from markets.browse_areas import compute_browse_area_slugs
    from markets.categories import _collect_tag_slugs

    Market = apps.get_model("markets", "Market")
    batch = []
    f1_tags = {"f1", "formula1"}
    for market in Market.objects.iterator(chunk_size=500):
        if not _collect_tag_slugs(market).intersection(f1_tags):
            continue
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
        ("markets", "0015_market_liquidity_total"),
    ]

    operations = [
        migrations.RunPython(
            backfill_formula1_browse_area_slugs,
            migrations.RunPython.noop,
        ),
    ]
