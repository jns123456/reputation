from django.core.management.base import BaseCommand, CommandError

from integrations.batch_services import HISTORICAL_BATCH_DATE
from integrations.eas_onchain import anchor_batch_onchain, onchain_ready
from integrations.models import AttestationBatch


class Command(BaseCommand):
    help = "Anchor an existing signed batch to EAS on Base."

    def add_arguments(self, parser):
        parser.add_argument(
            "--merkle-root",
            help="Merkle root of the batch to anchor.",
        )
        parser.add_argument(
            "--historical",
            action="store_true",
            help="Anchor the full-history genesis batch.",
        )
        parser.add_argument(
            "--latest",
            action="store_true",
            help="Anchor the most recently created batch.",
        )

    def handle(self, *args, **options):
        if not onchain_ready():
            raise CommandError(
                "On-chain anchoring is not configured. Set EAS_ANCHOR_PRIVATE_KEY and "
                "EAS_ONCHAIN_ANCHOR_ENABLED=True on Heroku."
            )

        batch = self._resolve_batch(options)
        if batch.status == AttestationBatch.Status.ANCHORED and batch.transaction_hash:
            self.stdout.write(
                self.style.WARNING(
                    f"Batch already anchored: tx={batch.transaction_hash} uid={batch.on_chain_uid}"
                )
            )
            return

        batch = anchor_batch_onchain(batch)
        if batch.status != AttestationBatch.Status.ANCHORED:
            raise CommandError(f"Anchoring failed; batch status={batch.status}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Anchored on Base: root={batch.merkle_root} tx={batch.transaction_hash} "
                f"uid={batch.on_chain_uid}"
            )
        )

    def _resolve_batch(self, options):
        flags = sum(bool(options[key]) for key in ("merkle_root", "historical", "latest"))
        if flags != 1:
            raise CommandError("Specify exactly one of --merkle-root, --historical, or --latest.")

        if options["historical"]:
            return AttestationBatch.objects.get(batch_date=HISTORICAL_BATCH_DATE)
        if options["latest"]:
            batch = AttestationBatch.objects.order_by("-created_at").first()
            if batch is None:
                raise CommandError("No batches found.")
            return batch
        return AttestationBatch.objects.get(merkle_root=options["merkle_root"])
