from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("markets", "0009_market_volume_24h"),
    ]

    operations = [
        migrations.AddField(
            model_name="market",
            name="title_es",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="market",
            name="description_es",
            field=models.TextField(blank=True),
        ),
    ]
