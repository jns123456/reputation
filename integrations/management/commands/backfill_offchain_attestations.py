from django.core.management.base import BaseCommand

from integrations.attestation_services import (
    record_prediction_claim_attestation,
    record_prediction_resolution_attestation,
    record_reputation_event_attestation,
)
from integrations.models import AttestationSchema, OffchainAttestation
from predictions.models import Prediction
from reputation.models import ReputationEvent


class Command(BaseCommand):
    help = "Backfill local offchain attestation records for existing forecasts."

    def handle(self, *args, **options):
        before_count = OffchainAttestation.objects.count()

        predictions = (
            Prediction.objects.exclude(status=Prediction.Status.VOID)
            .select_related("user", "market")
            .order_by("id")
        )
        for prediction in predictions:
            record_prediction_claim_attestation(prediction)
            if prediction.status == Prediction.Status.RESOLVED:
                record_prediction_resolution_attestation(prediction)

        events = (
            ReputationEvent.objects.select_related("user", "prediction", "prediction__market")
            .filter(
                event_type__in=[
                    ReputationEvent.EventType.CORRECT_PREDICTION,
                    ReputationEvent.EventType.INCORRECT_PREDICTION,
                ]
            )
            .order_by("id")
        )
        for event in events:
            record_reputation_event_attestation(event)

        after_count = OffchainAttestation.objects.count()
        created_count = after_count - before_count
        schema_count = AttestationSchema.objects.count()

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfilled offchain attestations: created={created_count}, "
                f"total={after_count}, schemas={schema_count}"
            )
        )
