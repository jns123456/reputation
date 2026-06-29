# Generated manually — Binance ID payouts and payment receipts

from django.db import migrations, models


def copy_wallet_to_binance(apps, schema_editor):
    ContestPayoutRequest = apps.get_model("reputation", "ContestPayoutRequest")
    for row in ContestPayoutRequest.objects.all().iterator():
        if getattr(row, "usdc_address", None):
            row.binance_id = row.usdc_address[:64]
            row.save(update_fields=["binance_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("reputation", "0012_contestpayoutrequest_chain_and_address"),
    ]

    operations = [
        migrations.RenameField(
            model_name="contestpayoutrequest",
            old_name="tx_hash",
            new_name="payment_reference",
        ),
        migrations.AddField(
            model_name="contestpayoutrequest",
            name="binance_id",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="contestpayoutrequest",
            name="payment_receipt",
            field=models.FileField(blank=True, upload_to="contest_payouts/receipts/%Y/%m/"),
        ),
        migrations.RunPython(copy_wallet_to_binance, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="contestpayoutrequest",
            name="usdc_address",
        ),
        migrations.RemoveField(
            model_name="contestpayoutrequest",
            name="chain",
        ),
        migrations.AlterField(
            model_name="contestpayoutrequest",
            name="binance_id",
            field=models.CharField(max_length=64),
        ),
        migrations.AlterField(
            model_name="contestpayoutrequest",
            name="payment_reference",
            field=models.CharField(
                blank=True,
                help_text="Optional Binance transfer ID or admin note reference.",
                max_length=128,
            ),
        ),
    ]
