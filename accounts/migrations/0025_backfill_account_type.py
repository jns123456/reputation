from django.db import migrations


def backfill_account_type(apps, schema_editor):
    """Map existing accounts onto the new classification (AGENTS.md §15).

    Legacy ``is_ai_agent`` accounts become ``declared_agent``; email-verified
    accounts get ``email_verified`` status. Everyone else stays ``human`` /
    ``unverified`` (the model defaults).
    """
    User = apps.get_model("accounts", "User")
    User.objects.filter(is_ai_agent=True).update(account_type="declared_agent")
    User.objects.filter(email_verified_at__isnull=False).update(
        verification_status="email_verified"
    )


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0024_aiagentprofile_agent_operator_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_account_type, reverse_noop),
    ]
