from django.db import migrations


class Migration(migrations.Migration):
    # Historically backfilled outcome labels for the now-removed Kalshi source.
    # Neutralized to a no-op after Kalshi support was dropped.
    dependencies = [
        ("markets", "0004_market_canonical_category_slug"),
    ]

    operations = [
        migrations.RunPython(migrations.RunPython.noop, migrations.RunPython.noop),
    ]
