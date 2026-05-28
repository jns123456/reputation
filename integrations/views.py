from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from integrations.attestation_services import verify_offchain_attestation
from integrations.models import OffchainAttestation


def _payload_timestamp(attestation, key):
    value = attestation.payload.get(key)
    if not value:
        return None
    return timezone.datetime.fromtimestamp(value, tz=timezone.get_current_timezone())


def attestation_detail(request, uid):
    attestation = get_object_or_404(
        OffchainAttestation.objects.select_related("schema", "prediction", "prediction__market", "user"),
        uid=uid,
    )
    payload_event_time = (
        _payload_timestamp(attestation, "created_at")
        or _payload_timestamp(attestation, "resolved_at")
        or _payload_timestamp(attestation, "as_of")
    )
    return render(
        request,
        "integrations/attestation_detail.html",
        {
            "attestation": attestation,
            "is_signature_valid": verify_offchain_attestation(attestation),
            "payload_event_time": payload_event_time,
        },
    )
