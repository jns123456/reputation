from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reputation", "0003_alter_popularityevent_event_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="reputationevent",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("correct_prediction", "Correct prediction"),
                    ("incorrect_prediction", "Incorrect prediction"),
                    ("exited_prediction", "Exited prediction"),
                    ("void_prediction", "Void prediction"),
                ],
                max_length=50,
            ),
        ),
    ]
