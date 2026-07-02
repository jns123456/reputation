# Generated migration for challenge invite tokens

import secrets

from django.db import migrations, models


def backfill_invite_tokens(apps, schema_editor):
    ChallengeParticipant = apps.get_model("challenges", "ChallengeParticipant")
    for participant in ChallengeParticipant.objects.filter(
        status="invited",
        invite_token="",
    ).iterator():
        participant.invite_token = secrets.token_urlsafe(16)
        participant.save(update_fields=["invite_token"])


class Migration(migrations.Migration):
    dependencies = [
        ("challenges", "0003_challenge_challenge_group"),
    ]

    operations = [
        migrations.AddField(
            model_name="challengeparticipant",
            name="invite_token",
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
        migrations.RunPython(backfill_invite_tokens, migrations.RunPython.noop),
    ]
