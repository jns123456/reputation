from django.db import migrations, models


def migrate_anonymous_profiles(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(is_anonymous_profile=True).update(identity_mode="anonymous")


def reverse_migrate_anonymous_profiles(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(identity_mode="anonymous").update(is_anonymous_profile=True)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0010_alter_bookmark_target_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="identity_mode",
            field=models.CharField(
                choices=[
                    ("public", "Public"),
                    ("pseudonym", "Pseudonym"),
                    ("anonymous", "Anonymous"),
                ],
                default="public",
                help_text="How the user appears publicly on the platform.",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="is_verified",
            field=models.BooleanField(
                default=False,
                help_text="Platform-verified identity (admin-granted).",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="verification_requested",
            field=models.BooleanField(
                default=False,
                help_text="User requested identity verification review.",
            ),
        ),
        migrations.RunPython(migrate_anonymous_profiles, reverse_migrate_anonymous_profiles),
        migrations.RemoveField(
            model_name="user",
            name="is_anonymous_profile",
        ),
    ]
