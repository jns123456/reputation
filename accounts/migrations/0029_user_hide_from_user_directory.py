from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0028_creatorprogram_creatorsubscription"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="hide_from_user_directory",
            field=models.BooleanField(
                default=False,
                help_text="When true, the account is omitted from the public user list and search.",
            ),
        ),
    ]
