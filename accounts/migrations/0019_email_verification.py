from django.db import migrations, models
import django.db.models.deletion


def mark_existing_users_email_verified(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    for user in User.objects.filter(email__gt="", email_verified_at__isnull=True).iterator():
        user.email_verified_at = user.created_at
        user.save(update_fields=["email_verified_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0018_notificationpreference_notify_push_pushsubscription"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="email_verified_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When the user confirmed ownership of their email address.",
                null=True,
            ),
        ),
        migrations.CreateModel(
            name="EmailVerificationToken",
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
                ("token", models.CharField(db_index=True, max_length=64, unique=True)),
                (
                    "email",
                    models.EmailField(
                        help_text="Email address snapshot at the time the token was issued.",
                        max_length=254,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="email_verification_tokens",
                        to="accounts.user",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["user", "-created_at"],
                        name="accounts_em_user_id_6f0a0d_idx",
                    )
                ],
            },
        ),
        migrations.RunPython(
            mark_existing_users_email_verified,
            migrations.RunPython.noop,
        ),
    ]
