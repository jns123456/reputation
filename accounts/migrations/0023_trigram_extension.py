from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0022_remove_user_avatar"),
    ]

    operations = [
        TrigramExtension(),
    ]
