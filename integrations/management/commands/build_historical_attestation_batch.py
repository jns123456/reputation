from django.core.management.base import BaseCommand

from integrations.batch_services import build_historical_attestation_batch


class Command(BaseCommand):
    help = "Build a genesis Merkle batch with every realized reputation position in platform history."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Rebuild the historical batch even if one already exists.",
        )

    def handle(self, *args, **options):
        batch, created = build_historical_attestation_batch(force=options["force"])
        status = "created" if created else "existing"
        self.stdout.write(
            self.style.SUCCESS(
                f"Historical batch {status}: root={batch.merkle_root} "
                f"records={batch.record_count} "
                f"period={batch.period_start.isoformat()} → {batch.period_end.isoformat()}"
            )
        )
