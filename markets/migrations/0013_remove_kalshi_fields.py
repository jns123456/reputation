from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("markets", "0012_market_accepting_orders_market_game_start_time"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="market",
            name="kalshi_ticker",
        ),
        migrations.RemoveField(
            model_name="market",
            name="kalshi_raw",
        ),
        migrations.RemoveField(
            model_name="market",
            name="kalshi_event_raw",
        ),
        migrations.RemoveField(
            model_name="market",
            name="kalshi_synced_at",
        ),
        migrations.AlterField(
            model_name="market",
            name="source",
            field=models.CharField(
                choices=[
                    ("polymarket", "Polymarket"),
                    ("manual", "Manual"),
                ],
                default="polymarket",
                max_length=50,
            ),
        ),
    ]
