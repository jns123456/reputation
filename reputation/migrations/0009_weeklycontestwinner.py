# Generated manually for weekly contest winners

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reputation", "0008_alter_popularityevent_event_type_seasonaward"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WeeklyContestWinner",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("week_code", models.CharField(max_length=10)),
                (
                    "prize_type",
                    models.CharField(
                        choices=[
                            ("absolute", "Absolute reputation points"),
                            ("relative", "Reputation per forecast"),
                        ],
                        max_length=20,
                    ),
                ),
                ("reputation_points", models.IntegerField(default=0)),
                ("reputation_score", models.FloatField(default=0)),
                ("scored_forecast_count", models.PositiveIntegerField(default=0)),
                ("prize_usd", models.PositiveSmallIntegerField(default=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="weekly_contest_wins",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-week_code", "prize_type"],
                "indexes": [
                    models.Index(
                        fields=["week_code", "prize_type"],
                        name="reputation__week_co_6a1b2c_idx",
                    ),
                    models.Index(
                        fields=["user", "-created_at"],
                        name="reputation__user_id_7d3e4f_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("week_code", "prize_type"),
                        name="weeklycontestwinner_unique_week_prize",
                    ),
                ],
            },
        ),
    ]
