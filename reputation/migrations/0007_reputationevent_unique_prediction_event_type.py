from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reputation", "0006_popularityevent_reputation__user_id_664e3f_idx_and_more"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="reputationevent",
            constraint=models.UniqueConstraint(
                fields=("prediction", "event_type"),
                name="reputationevent_unique_prediction_event_type",
            ),
        ),
    ]
