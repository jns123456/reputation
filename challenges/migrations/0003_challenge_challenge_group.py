import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("challenges", "0002_challengegroup"),
    ]

    operations = [
        migrations.AddField(
            model_name="challenge",
            name="challenge_group",
            field=models.ForeignKey(
                blank=True,
                help_text="When set, the challenge activates after the first invited member accepts.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="challenges",
                to="challenges.challengegroup",
            ),
        ),
    ]
