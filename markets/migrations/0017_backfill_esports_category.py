from django.db import migrations


def backfill_esports_market_categories(apps, schema_editor):
    from markets.browse_areas import compute_browse_area_slugs
    from markets.categories import resolve_market_category_slug

    Market = apps.get_model("markets", "Market")
    batch = []
    for market in Market.objects.iterator(chunk_size=500):
        slug = resolve_market_category_slug(market)
        slugs = compute_browse_area_slugs(market)
        changed = False
        if market.canonical_category_slug != slug:
            market.canonical_category_slug = slug
            changed = True
        if market.browse_area_slugs != slugs:
            market.browse_area_slugs = slugs
            changed = True
        if changed:
            batch.append(market)
        if len(batch) >= 500:
            Market.objects.bulk_update(batch, ["canonical_category_slug", "browse_area_slugs"])
            batch = []
    if batch:
        Market.objects.bulk_update(batch, ["canonical_category_slug", "browse_area_slugs"])


class Migration(migrations.Migration):
    dependencies = [
        ("markets", "0016_backfill_formula1_browse_area"),
    ]

    operations = [
        migrations.RunPython(backfill_esports_market_categories, migrations.RunPython.noop),
    ]
