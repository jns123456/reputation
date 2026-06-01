# Generated migration for daily EAS batch fields

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="attestationbatch",
            name="on_chain_uid",
            field=models.CharField(blank=True, max_length=66),
        ),
        migrations.AddField(
            model_name="attestationbatch",
            name="payload_hash",
            field=models.CharField(blank=True, max_length=66),
        ),
        migrations.AddField(
            model_name="attestationbatch",
            name="batch_date",
            field=models.DateField(db_index=True, default=django.utils.timezone.localdate),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="attestationbatch",
            name="period_end",
            field=models.DateTimeField(default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="attestationbatch",
            name="period_start",
            field=models.DateTimeField(default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="attestationbatch",
            name="prev_batch_root",
            field=models.CharField(blank=True, max_length=66),
        ),
        migrations.AddField(
            model_name="attestationbatch",
            name="record_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="attestationbatch",
            name="records",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="attestationbatch",
            name="score_version",
            field=models.PositiveSmallIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="attestationbatch",
            name="signature",
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name="attestationbatch",
            name="signer",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="attestationbatch",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("signed", "Signed off-chain"),
                    ("anchored", "Anchored on-chain"),
                    ("failed", "Failed"),
                ],
                db_index=True,
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AlterModelOptions(
            name="attestationbatch",
            options={"ordering": ["-batch_date"]},
        ),
        migrations.AlterField(
            model_name="attestationbatch",
            name="batch_date",
            field=models.DateField(db_index=True, unique=True),
        ),
    ]
