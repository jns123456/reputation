from django.db import migrations


def backfill_esports_market_categories(apps, schema_editor):
    from markets.browse_areas import compute_browse_area_slugs
    from markets.categories import _collect_tag_slugs, resolve_market_category_slug

    Market = apps.get_model("markets", "Market")
    esports_tags = frozenset(
        {
            "esports",
            "counter-strike-2",
            "cs2",
            "counter-strike",
            "valorant",
            "league-of-legends",
            "lol",
            "dota-2",
            "mobile-legends-bang-bang",
            "overwatch",
            "rainbow-six-siege",
            "honor-of-kings",
            "call-of-duty",
            "cod",
            "rocket-league",
            "starcraft-2",
            "starcraft-ii",
            "starcraft-brood-war",
        }
    )
    batch = []
    for market in Market.objects.only(
        "id",
        "canonical_category_slug",
        "browse_area_slugs",
        "polymarket_event_raw",
        "polymarket_raw",
        "category",
    ).iterator(chunk_size=100):
        tag_slugs = _collect_tag_slugs(market)
        if not tag_slugs.intersection(esports_tags):
            continue
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
        if len(batch) >= 100:
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
