from django.core.management.base import BaseCommand

from integrations.eas_onchain import ensure_daily_batch_schema_registered, onchain_ready


class Command(BaseCommand):
    help = "Register the PredictStamp daily batch schema on Base EAS (one-time)."

    def handle(self, *args, **options):
        schema_uid = ensure_daily_batch_schema_registered()
        if onchain_ready():
            self.stdout.write(
                self.style.SUCCESS(f"Daily batch schema ready on Base: {schema_uid}")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Computed schema UID locally: {schema_uid}. "
                    "Set EAS_ANCHOR_PRIVATE_KEY and EAS_ONCHAIN_ANCHOR_ENABLED=True to register on-chain."
                )
            )
