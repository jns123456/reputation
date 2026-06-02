from django.db import migrations, models


def backfill_reputation_scores(apps, schema_editor):
    UserProfile = apps.get_model("accounts", "UserProfile")
    ReputationEvent = apps.get_model("reputation", "ReputationEvent")

    from reputation.services import calculate_reputation_score

    scored_types = [
        "correct_prediction",
        "incorrect_prediction",
        "exited_prediction",
    ]

    profile_counts = {}
    for row in (
        ReputationEvent.objects.filter(event_type__in=scored_types)
        .values("user_id", "prediction_id")
        .distinct()
    ):
        profile_counts[row["user_id"]] = profile_counts.get(row["user_id"], 0) + 1

    for profile in UserProfile.objects.all().iterator():
        scored = profile_counts.get(profile.user_id, 0)
        profile.scored_forecast_count = scored
        profile.reputation_score = calculate_reputation_score(
            reputation_points=profile.reputation_points,
            scored_forecast_count=scored,
        )
        profile.save(update_fields=["scored_forecast_count", "reputation_score", "updated_at"])

    UserCategoryStats = apps.get_model("accounts", "UserCategoryStats")
    for stats in UserCategoryStats.objects.all().iterator():
        scored = (
            ReputationEvent.objects.filter(
                user_id=stats.user_id,
                event_type__in=scored_types,
                prediction__market__canonical_category_slug=stats.category_slug,
            )
            .values("prediction_id")
            .distinct()
            .count()
        )
        stats.scored_forecast_count = scored
        stats.reputation_score = calculate_reputation_score(
            reputation_points=stats.reputation_points,
            scored_forecast_count=scored,
        )
        stats.save(update_fields=["scored_forecast_count", "reputation_score", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0026_userprofile_accounts_us_reputat_06b003_idx_and_more"),
        ("reputation", "0005_alter_popularityevent_event_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="scored_forecast_count",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Forecasts that received reputation scoring (resolved or exited).",
            ),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="reputation_score",
            field=models.FloatField(
                default=0.0,
                help_text="Average reputation P&L per scored forecast (ranking metric).",
            ),
        ),
        migrations.AddField(
            model_name="usercategorystats",
            name="scored_forecast_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(backfill_reputation_scores, migrations.RunPython.noop),
    ]
