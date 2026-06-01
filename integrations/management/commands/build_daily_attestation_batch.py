from django.core.management.base import BaseCommand

from integrations.batch_services import build_daily_attestation_batch


class Command(BaseCommand):
    help = "Build the daily EAS Merkle batch for the last 24 hours of realized reputation."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Rebuild even if a batch already exists for this period end.",
        )

    def handle(self, *args, **options):
        batch, created = build_daily_attestation_batch(force=options["force"])
        status = "created" if created else "existing"
        self.stdout.write(
            self.style.SUCCESS(
                f"Daily batch {status}: root={batch.merkle_root} "
                f"records={batch.record_count} "
                f"period={batch.period_start.isoformat()} → {batch.period_end.isoformat()}"
            )
        )
