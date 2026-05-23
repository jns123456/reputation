from django.db import migrations, models


def backfill_canonical_category_slug(apps, schema_editor):
    Market = apps.get_model("markets", "Market")
    from markets.categories import resolve_market_category_slug

    batch = []
    for market in Market.objects.iterator(chunk_size=500):
        slug = resolve_market_category_slug(market)
        if market.canonical_category_slug != slug:
            market.canonical_category_slug = slug
            batch.append(market)
        if len(batch) >= 500:
            Market.objects.bulk_update(batch, ["canonical_category_slug"])
            batch.clear()
    if batch:
        Market.objects.bulk_update(batch, ["canonical_category_slug"])


class Migration(migrations.Migration):
    dependencies = [
        ("markets", "0003_market_kalshi_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="market",
            name="canonical_category_slug",
            field=models.CharField(blank=True, db_index=True, max_length=50),
        ),
        migrations.RunPython(backfill_canonical_category_slug, migrations.RunPython.noop),
        migrations.AddIndex(
            model_name="market",
            index=models.Index(
                fields=["status", "canonical_category_slug"],
                name="markets_mar_status_8a1f2c_idx",
            ),
        ),
    ]
