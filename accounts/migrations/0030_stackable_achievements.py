"""Allow multiple rows per achievement code and track streak milestone completions."""

from collections import Counter

from django.db import migrations, models


ONE_TIME_ACHIEVEMENT_CODES = frozenset(
    {"first_forecast", "first_correct", "challenge_win_1"}
)

STACKABLE_METRICS = {
    "forecaster_10": ("prediction_count", 10),
    "forecaster_50": ("prediction_count", 50),
    "sharp_10": ("correct_prediction_count", 10),
    "popular_100": ("popularity_points", 100),
    "popular_500": ("popularity_points", 500),
    "challenge_win_5": ("challenges_won", 5),
    "challenge_win_10": ("challenges_won", 10),
    "streak_7": ("streak_7_completions", 1),
    "streak_30": ("streak_30_completions", 1),
}


def _target_stack_count(code, stats):
    key, threshold = STACKABLE_METRICS[code]
    value = stats.get(key, 0) or 0
    if threshold <= 1:
        return int(value)
    return int(value) // threshold


def _collect_stats(user, profile, streak, challenges_won):
    return {
        "prediction_count": getattr(profile, "prediction_count", 0) or 0,
        "correct_prediction_count": getattr(profile, "correct_prediction_count", 0) or 0,
        "popularity_points": getattr(profile, "popularity_points", 0) or 0,
        "streak_7_completions": getattr(streak, "streak_7_completions", 0) or 0,
        "streak_30_completions": getattr(streak, "streak_30_completions", 0) or 0,
        "challenges_won": challenges_won,
    }


def backfill_streak_counters_and_achievements(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    UserProfile = apps.get_model("accounts", "UserProfile")
    ActivityStreak = apps.get_model("accounts", "ActivityStreak")
    UserAchievement = apps.get_model("accounts", "UserAchievement")
    Challenge = apps.get_model("challenges", "Challenge")

    for streak in ActivityStreak.objects.all().iterator():
        updates = {}
        if streak.longest_streak >= 7:
            updates["streak_7_completions"] = max(
                streak.streak_7_completions,
                streak.longest_streak // 7,
            )
        if streak.longest_streak >= 30:
            updates["streak_30_completions"] = max(
                streak.streak_30_completions,
                streak.longest_streak // 30,
            )
        if updates:
            for field, value in updates.items():
                setattr(streak, field, value)
            streak.save(update_fields=[*updates.keys(), "updated_at"])

    for user in User.objects.all().iterator():
        try:
            profile = UserProfile.objects.get(user_id=user.id)
        except UserProfile.DoesNotExist:
            continue

        streak = ActivityStreak.objects.filter(user_id=user.id).first()
        challenges_won = Challenge.objects.filter(
            winner_id=user.id,
            status="completed",
        ).count()
        stats = _collect_stats(user, profile, streak, challenges_won)
        earned_counts = Counter(
            UserAchievement.objects.filter(user_id=user.id).values_list("code", flat=True)
        )

        for code, (key, threshold) in STACKABLE_METRICS.items():
            target = _target_stack_count(code, stats)
            current = earned_counts.get(code, 0)
            while current < target:
                UserAchievement.objects.create(user_id=user.id, code=code)
                current += 1


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0029_user_hide_from_user_directory"),
        ("challenges", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="activitystreak",
            name="streak_7_completions",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Times the user reached a 7-day streak milestone (stackable Week Warrior).",
            ),
        ),
        migrations.AddField(
            model_name="activitystreak",
            name="streak_30_completions",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Times the user reached a 30-day streak milestone (stackable Unstoppable).",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="userachievement",
            unique_together=set(),
        ),
        migrations.RunPython(
            backfill_streak_counters_and_achievements,
            migrations.RunPython.noop,
        ),
    ]
