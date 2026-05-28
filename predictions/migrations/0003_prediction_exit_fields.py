from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("predictions", "0002_prediction_predicted_direction"),
    ]

    operations = [
        migrations.AddField(
            model_name="prediction",
            name="exited_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="prediction",
            name="probability_at_exit_time",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="prediction",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("resolved", "Resolved"),
                    ("exited", "Exited"),
                    ("void", "Void"),
                ],
                db_index=True,
                default="pending",
                max_length=20,
            ),
        ),
    ]
