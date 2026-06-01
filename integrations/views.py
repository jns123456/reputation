from django.shortcuts import get_object_or_404, render

from integrations.attestation_services import verify_offchain_attestation
from integrations.batch_services import get_batch_stats, is_historical_batch, verify_merkle_proof
from integrations.models import AttestationBatch, OffchainAttestation


def _payload_timestamp(attestation, key):
    from django.utils import timezone

    value = attestation.payload.get(key)
    if not value:
        return None
    return timezone.datetime.fromtimestamp(value, tz=timezone.get_current_timezone())


def proof_index(request):
    stats = get_batch_stats()
    recent_batches = AttestationBatch.objects.order_by("-created_at")[:12]
    return render(
        request,
        "integrations/proof_index.html",
        {
            "stats": stats,
            "recent_batches": recent_batches,
        },
    )


def batch_detail(request, merkle_root):
    batch = get_object_or_404(AttestationBatch, merkle_root=merkle_root)
    records = []
    for record in batch.records:
        leaf_hash = record.get("leaf_hash", "")
        proof = record.get("merkle_proof", [])
        records.append(
            {
                **record,
                "proof_valid": verify_merkle_proof(
                    leaf_hash=leaf_hash,
                    proof=proof,
                    root=batch.merkle_root,
                )
                if leaf_hash
                else False,
            }
        )
    return render(
        request,
        "integrations/batch_detail.html",
        {
            "batch": batch,
            "records": records,
            "signature_valid": batch.is_signature_valid,
            "is_historical": is_historical_batch(batch),
        },
    )


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
