from django.db import migrations, models


def mark_existing_users_onboarded(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.update(onboarding_completed=True)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0011_user_identity_mode"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="onboarding_completed",
            field=models.BooleanField(
                default=False,
                help_text="Whether the user finished first-time profile and identity setup.",
            ),
        ),
        migrations.RunPython(mark_existing_users_onboarded, migrations.RunPython.noop),
    ]
