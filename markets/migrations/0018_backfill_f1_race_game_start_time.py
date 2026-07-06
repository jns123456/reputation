"""Backfill ``game_start_time`` for F1 Grand Prix markets imported before kickoff gating."""

from django.db import migrations


def _is_f1_race_market(market) -> bool:
    tags = set()
    for payload in (market.polymarket_event_raw or {}, market.polymarket_raw or {}):
        for tag in payload.get("tags") or []:
            if isinstance(tag, dict) and tag.get("slug"):
                tags.add(str(tag["slug"]).casefold())
            elif tag:
                tags.add(str(tag).casefold())
    if not tags.intersection({"f1", "formula1"}):
        return False
    if tags.intersection({"grand-prix"}):
        return True
    return "grand prix" in (market.title or "").casefold()


def backfill_f1_race_game_start_times(apps, schema_editor):
    Market = apps.get_model("markets", "Market")
    to_update = []
    for market in Market.objects.filter(game_start_time__isnull=True, close_date__isnull=False):
        if not _is_f1_race_market(market):
            continue
        market.game_start_time = market.close_date
        to_update.append(market)
    if to_update:
        Market.objects.bulk_update(to_update, ["game_start_time"])


class Migration(migrations.Migration):
    dependencies = [
        ("markets", "0017_backfill_esports_category"),
    ]

    operations = [
        migrations.RunPython(backfill_f1_race_game_start_times, migrations.RunPython.noop),
    ]
