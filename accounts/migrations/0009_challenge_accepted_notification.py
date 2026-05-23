from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0008_challenge_notifications"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="notification_type",
            field=models.CharField(
                choices=[
                    ("followed_user_prediction", "Followed user prediction"),
                    ("new_follower", "New follower"),
                    ("upvote_received", "Upvote received"),
                    ("downvote_received", "Downvote received"),
                    ("prediction_resolved", "Prediction resolved"),
                    ("challenge_invitation", "Challenge invitation"),
                    ("challenge_market_resolved", "Challenge event resolved"),
                    ("challenge_completed", "Challenge completed"),
                    ("challenge_accepted", "Challenge accepted"),
                ],
                max_length=40,
            ),
        ),
        migrations.AddConstraint(
            model_name="notification",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("challenge__isnull", False),
                    ("notification_type", "challenge_accepted"),
                ),
                fields=("recipient", "notification_type", "challenge", "actor"),
                name="unique_challenge_accepted_notification",
            ),
        ),
    ]
