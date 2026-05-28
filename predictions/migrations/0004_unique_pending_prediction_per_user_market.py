from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("predictions", "0003_prediction_exit_fields"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="prediction",
            constraint=models.UniqueConstraint(
                fields=("user", "market"),
                condition=Q(status="pending"),
                name="unique_pending_prediction_per_user_market",
            ),
        ),
    ]
