from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("predictions", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="prediction",
            name="predicted_direction",
            field=models.CharField(
                choices=[("yes", "Yes"), ("no", "No")],
                default="yes",
                max_length=10,
            ),
        ),
    ]
