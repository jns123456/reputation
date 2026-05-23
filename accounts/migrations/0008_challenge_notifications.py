# Generated manually for challenge notifications

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("challenges", "0001_initial"),
        ("markets", "0006_rename_markets_mar_status_8a1f2c_idx_markets_mar_status_9d704b_idx"),
        ("accounts", "0007_prediction_resolved_notifications"),
    ]

    operations = [
        migrations.AddField(
            model_name="notificationpreference",
            name="notify_challenge_updates",
            field=models.BooleanField(
                default=True,
                help_text="Receive alerts about challenge invitations, event resolutions, and results.",
            ),
        ),
        migrations.AddField(
            model_name="notification",
            name="challenge",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="notifications",
                to="challenges.challenge",
            ),
        ),
        migrations.AddField(
            model_name="notification",
            name="market",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="challenge_notifications",
                to="markets.market",
            ),
        ),
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
                ],
                max_length=40,
            ),
        ),
        migrations.AddConstraint(
            model_name="notification",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("challenge__isnull", False),
                    ("market__isnull", False),
                    ("notification_type", "challenge_market_resolved"),
                ),
                fields=("recipient", "notification_type", "challenge", "market"),
                name="unique_challenge_market_notification",
            ),
        ),
        migrations.AddConstraint(
            model_name="notification",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("challenge__isnull", False),
                    ("notification_type", "challenge_completed"),
                ),
                fields=("recipient", "notification_type", "challenge"),
                name="unique_challenge_completed_notification",
            ),
        ),
        migrations.AddConstraint(
            model_name="notification",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("challenge__isnull", False),
                    ("notification_type", "challenge_invitation"),
                ),
                fields=("recipient", "notification_type", "challenge"),
                name="unique_challenge_invitation_notification",
            ),
        ),
    ]
