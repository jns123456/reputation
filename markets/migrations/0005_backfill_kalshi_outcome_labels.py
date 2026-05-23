from django.db import migrations


def backfill_kalshi_outcome_labels(apps, schema_editor):
    Market = apps.get_model("markets", "Market")
    from integrations.kalshi.client import normalize_kalshi_record

    batch = []
    for market in Market.objects.filter(source="kalshi").exclude(kalshi_raw={}).iterator(chunk_size=200):
        normalized = normalize_kalshi_record(
            market.kalshi_raw,
            default_category=market.category or "",
            raw_event=market.kalshi_event_raw or None,
        )
        market.outcomes = normalized["outcomes"]
        market.current_probability = normalized["current_probability"]
        batch.append(market)
        if len(batch) >= 200:
            Market.objects.bulk_update(batch, ["outcomes", "current_probability"])
            batch.clear()
    if batch:
        Market.objects.bulk_update(batch, ["outcomes", "current_probability"])


class Migration(migrations.Migration):
    dependencies = [
        ("markets", "0004_market_canonical_category_slug"),
    ]

    operations = [
        migrations.RunPython(backfill_kalshi_outcome_labels, migrations.RunPython.noop),
    ]
