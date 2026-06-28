# Generated manually — payout chain choices and longer wallet addresses

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reputation", "0011_weeklycontestwinner_notified_at"),
    ]

    operations = [
        migrations.AlterField(
            model_name="contestpayoutrequest",
            name="usdc_address",
            field=models.CharField(max_length=128),
        ),
        migrations.AlterField(
            model_name="contestpayoutrequest",
            name="chain",
            field=models.CharField(
                choices=[
                    ("ethereum", "Ethereum (ERC-20)"),
                    ("base", "Base"),
                    ("polygon", "Polygon"),
                    ("bsc", "BNB Smart Chain (BEP-20)"),
                    ("arbitrum", "Arbitrum"),
                    ("optimism", "Optimism"),
                    ("tron", "Tron (TRC-20)"),
                    ("solana", "Solana"),
                ],
                default="base",
                max_length=20,
            ),
        ),
    ]
