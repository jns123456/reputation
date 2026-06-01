"""Local-first EAS-shaped offchain attestation services."""

import hashlib
import hmac
import json
import logging
from datetime import datetime

from django.conf import settings
from django.db import IntegrityError
from django.utils import timezone

from integrations.models import AttestationSchema, OffchainAttestation
from reputation.services import get_predicted_outcome_probability

logger = logging.getLogger(__name__)

ZERO_UID = "0x" + "0" * 64

SCHEMA_DEFINITIONS = {
    AttestationSchema.Kind.PREDICTION_CLAIM: {
        "name": "Prediction claim",
        "schema": (
            "uint256 predictionId,bytes32 marketId,string predictedOutcome,"
            "string predictedDirection,uint16 confidenceBps,uint16 probabilityBps,"
            "uint64 createdAt,bytes32 contentHash"
        ),
    },
    AttestationSchema.Kind.PREDICTION_RESOLUTION: {
        "name": "Prediction resolution",
        "schema": (
            "uint256 predictionId,bytes32 marketId,string resolvedOutcome,"
            "bool isCorrect,uint64 resolvedAt,bytes32 sourceHash"
        ),
    },
    AttestationSchema.Kind.REPUTATION_EVENT: {
        "name": "Reputation event",
        "schema": (
            "uint256 eventId,bytes32 userIdHash,bytes32 predictionUid,"
            "int256 pointsDelta,uint16 scoreVersion,bytes32 reasonHash"
        ),
    },
    AttestationSchema.Kind.PROFILE_SUMMARY: {
        "name": "Profile reputation summary",
        "schema": (
            "bytes32 userIdHash,int256 reputationPoints,uint32 predictionCount,"
            "uint32 correctCount,uint32 incorrectCount,uint64 asOf,bytes32 eventRoot"
        ),
    },
    AttestationSchema.Kind.DAILY_BATCH_ANCHOR: {
        "name": "Daily batch anchor",
        "schema": (
            "bytes32 batchRoot,uint32 recordCount,uint64 periodStart,uint64 periodEnd,"
            "uint16 scoreVersion,bytes32 prevBatchRoot"
        ),
    },
}


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=_json_default)


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _hash(value):
    if not isinstance(value, bytes):
        value = str(value).encode("utf-8")
    return "0x" + hashlib.sha256(value).hexdigest()


def _hash_json(value):
    return _hash(canonical_json(value).encode("utf-8"))


def _sign(value):
    signing_key = getattr(settings, "EAS_OFFCHAIN_SIGNING_KEY", settings.SECRET_KEY)
    return hmac.new(
        signing_key.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _signer_id():
    return getattr(settings, "EAS_ATTESTER_ID", "proofrep-platform-v1")


def _chain_id():
    return getattr(settings, "EAS_CHAIN_ID", 0)


def _verifying_contract():
    return getattr(settings, "EAS_VERIFYING_CONTRACT", "")


def _schema_uid(kind, schema):
    return _hash(f"proofrep:eas:schema:v1:{kind}:{schema}")


def get_or_create_attestation_schema(kind):
    definition = SCHEMA_DEFINITIONS[kind]
    schema_uid = _schema_uid(kind, definition["schema"])
    schema, _ = AttestationSchema.objects.get_or_create(
        kind=kind,
        version=1,
        defaults={
            "name": definition["name"],
            "schema": definition["schema"],
            "schema_uid": schema_uid,
            "chain_id": _chain_id(),
            "verifying_contract": _verifying_contract(),
        },
    )
    return schema


def _user_id_hash(user_id):
    return _hash(f"proofrep:user:{user_id}")


def _market_id_hash(market):
    stable_id = market.external_id or f"local:{market.pk}"
    return _hash(f"{market.source}:{stable_id}")


def _timestamp(value):
    if value is None:
        return 0
    return int(value.timestamp())


def _prediction_content_hash(prediction):
    return _hash_json(
        {
            "market_title": prediction.market.title,
            "reasoning": prediction.reasoning,
            "prediction_id": prediction.id,
        }
    )


def _prediction_probability_bps(prediction):
    probability = get_predicted_outcome_probability(
        prediction.predicted_outcome,
        prediction.probability_at_prediction_time,
        predicted_direction=prediction.predicted_direction,
    )
    return int(round(probability * 10000))


def build_prediction_claim_payload(prediction):
    return {
        "prediction_id": prediction.id,
        "market_id": _market_id_hash(prediction.market),
        "predicted_outcome": prediction.predicted_outcome,
        "predicted_direction": prediction.predicted_direction,
        "confidence_bps": int(round(prediction.confidence * 10000)),
        "probability_bps": _prediction_probability_bps(prediction),
        "created_at": _timestamp(prediction.created_at),
        "content_hash": _prediction_content_hash(prediction),
    }


def build_prediction_resolution_payload(prediction):
    return {
        "prediction_id": prediction.id,
        "market_id": _market_id_hash(prediction.market),
        "resolved_outcome": prediction.market.resolved_outcome,
        "is_correct": bool(prediction.is_correct),
        "resolved_at": _timestamp(prediction.resolved_at),
        "source_hash": _hash_json(
            {
                "market_id": prediction.market.id,
                "resolved_outcome": prediction.market.resolved_outcome,
                "status": prediction.market.status,
            }
        ),
    }


def build_reputation_event_payload(event, prediction_uid):
    return {
        "event_id": event.id,
        "user_id_hash": _user_id_hash(event.user_id),
        "prediction_uid": prediction_uid,
        "points_delta": event.points_delta,
        "score_version": 1,
        "reason_hash": _hash(event.reason),
    }


def create_offchain_attestation(
    *,
    kind,
    payload,
    prediction=None,
    reputation_event=None,
    user=None,
    ref_uid=ZERO_UID,
    recipient="",
):
    schema = get_or_create_attestation_schema(kind)
    existing = _find_existing_attestation(
        schema=schema,
        prediction=prediction,
        reputation_event=reputation_event,
    )
    if existing:
        return existing

    payload_hash = _hash_json(payload)
    now = timezone.now()
    signer = _signer_id()
    message = {
        "version": 1,
        "schema": schema.schema_uid,
        "recipient": recipient,
        "time": _timestamp(now),
        "expirationTime": 0,
        "revocable": True,
        "refUID": ref_uid,
        "data": payload_hash,
        "payload": payload,
    }
    signature = _sign(canonical_json(message))
    uid = _hash_json(
        {
            "schema": schema.schema_uid,
            "payload_hash": payload_hash,
            "signature": signature,
            "signer": signer,
        }
    )
    raw_attestation = {
        "sig": {
            "domain": {
                "name": "PredictStamp EAS Offchain",
                "version": "1",
                "chainId": schema.chain_id,
                "verifyingContract": schema.verifying_contract,
            },
            "primaryType": "Attest",
            "uid": uid,
            "message": message,
        },
        "signer": signer,
        "signature": signature,
    }

    try:
        return OffchainAttestation.objects.create(
            schema=schema,
            uid=uid,
            signer=signer,
            recipient=recipient,
            ref_uid=ref_uid,
            payload=payload,
            payload_hash=payload_hash,
            signature=signature,
            raw_attestation=raw_attestation,
            status=OffchainAttestation.Status.VERIFIED,
            prediction=prediction,
            reputation_event=reputation_event,
            user=user,
            verified_at=now,
        )
    except IntegrityError:
        return OffchainAttestation.objects.get(uid=uid)


def _find_existing_attestation(*, schema, prediction=None, reputation_event=None):
    qs = OffchainAttestation.objects.filter(schema=schema)
    if reputation_event is not None:
        return qs.filter(reputation_event=reputation_event).first()
    if prediction is not None:
        return qs.filter(prediction=prediction).first()
    return None


def verify_offchain_attestation(attestation):
    message = attestation.raw_attestation.get("sig", {}).get("message", {})
    payload = message.get("payload", {})
    payload_hash = _hash_json(payload)
    expected_signature = _sign(canonical_json(message))
    return (
        payload_hash == attestation.payload_hash
        and expected_signature == attestation.signature
        and message.get("schema") == attestation.schema.schema_uid
    )


def record_prediction_claim_attestation(prediction):
    payload = build_prediction_claim_payload(prediction)
    return create_offchain_attestation(
        kind=AttestationSchema.Kind.PREDICTION_CLAIM,
        payload=payload,
        prediction=prediction,
        user=prediction.user,
    )


def record_prediction_resolution_attestation(prediction):
    payload = build_prediction_resolution_payload(prediction)
    claim = prediction.verified_attestation
    ref_uid = claim.uid if claim else ZERO_UID
    return create_offchain_attestation(
        kind=AttestationSchema.Kind.PREDICTION_RESOLUTION,
        payload=payload,
        prediction=prediction,
        user=prediction.user,
        ref_uid=ref_uid,
    )


def record_reputation_event_attestation(event):
    prediction = event.prediction
    claim = prediction.verified_attestation
    prediction_uid = claim.uid if claim else ZERO_UID
    payload = build_reputation_event_payload(event, prediction_uid)
    return create_offchain_attestation(
        kind=AttestationSchema.Kind.REPUTATION_EVENT,
        payload=payload,
        prediction=prediction,
        reputation_event=event,
        user=event.user,
        ref_uid=prediction_uid,
    )


def record_prediction_claim_attestation_safely(prediction):
    try:
        return record_prediction_claim_attestation(prediction)
    except Exception:
        logger.exception("Failed to record prediction claim attestation for %s", prediction.id)
        return None


def record_prediction_resolution_attestation_safely(prediction):
    try:
        return record_prediction_resolution_attestation(prediction)
    except Exception:
        logger.exception("Failed to record prediction resolution attestation for %s", prediction.id)
        return None


def record_reputation_event_attestation_safely(event):
    try:
        return record_reputation_event_attestation(event)
    except Exception:
        logger.exception("Failed to record reputation event attestation for %s", event.id)
        return None
