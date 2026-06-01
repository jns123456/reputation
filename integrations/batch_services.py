"""Daily EAS batch: Merkle commitments of realized reputation positions."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from integrations.attestation_services import (
    _hash,
    _hash_json,
    _market_id_hash,
    _sign,
    _signer_id,
    _timestamp,
    _user_id_hash,
    canonical_json,
)
from integrations.models import AttestationBatch
from reputation.models import ReputationEvent
from reputation.services import get_predicted_outcome_probability

logger = logging.getLogger(__name__)

SCORE_VERSION = 1
HISTORICAL_BATCH_DATE = date(1970, 1, 1)
REALIZED_EVENT_TYPES = (
    ReputationEvent.EventType.EXITED_PREDICTION,
    ReputationEvent.EventType.CORRECT_PREDICTION,
    ReputationEvent.EventType.INCORRECT_PREDICTION,
)

CLOSE_TYPE_MAP = {
    ReputationEvent.EventType.EXITED_PREDICTION: "exited",
    ReputationEvent.EventType.CORRECT_PREDICTION: "resolved_correct",
    ReputationEvent.EventType.INCORRECT_PREDICTION: "resolved_incorrect",
}


def _entry_probability_bps(prediction):
    probability = get_predicted_outcome_probability(
        prediction.predicted_outcome,
        prediction.probability_at_prediction_time,
        predicted_direction=prediction.predicted_direction,
    )
    return int(round(probability * 10000))


def _close_probability_bps(prediction, event):
    if event.event_type == ReputationEvent.EventType.EXITED_PREDICTION:
        probability = get_predicted_outcome_probability(
            prediction.predicted_outcome,
            prediction.probability_at_exit_time,
            predicted_direction=prediction.predicted_direction,
        )
        return int(round(probability * 10000))
    if prediction.is_correct:
        return 10000
    return 0


def _closed_at_timestamp(prediction, event):
    if event.event_type == ReputationEvent.EventType.EXITED_PREDICTION:
        return _timestamp(prediction.exited_at)
    return _timestamp(prediction.resolved_at) or _timestamp(event.created_at)


def build_position_close_record(reputation_event):
    """One leaf: user entered a market, closed the position, earned/lost reputation."""
    prediction = reputation_event.prediction
    market = prediction.market
    return {
        "reputation_event_id": reputation_event.id,
        "prediction_id": prediction.id,
        "user_id_hash": _user_id_hash(reputation_event.user_id),
        "market_id_hash": _market_id_hash(market),
        "market_title_hash": _hash(market.title),
        "predicted_outcome": prediction.predicted_outcome,
        "predicted_direction": prediction.predicted_direction,
        "entry_probability_bps": _entry_probability_bps(prediction),
        "close_type": CLOSE_TYPE_MAP[reputation_event.event_type],
        "close_probability_bps": _close_probability_bps(prediction, reputation_event),
        "points_delta": reputation_event.points_delta,
        "score_version": SCORE_VERSION,
        "entry_at": _timestamp(prediction.created_at),
        "closed_at": _closed_at_timestamp(prediction, reputation_event),
    }


def hash_position_close_record(record):
    return _hash_json(record)


def _hash_pair(left_hash, right_hash):
    left_bytes = left_hash.removeprefix("0x")
    right_bytes = right_hash.removeprefix("0x")
    return _hash(bytes.fromhex(left_bytes) + bytes.fromhex(right_bytes))


def compute_merkle_root(leaf_hashes):
    """Binary Merkle tree over sorted leaf hashes (PredictStamp v1)."""
    if not leaf_hashes:
        return _hash("proofrep:eas:empty-batch:v1")

    layer = sorted(leaf_hashes)
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        next_layer = []
        for index in range(0, len(layer), 2):
            next_layer.append(_hash_pair(layer[index], layer[index + 1]))
        layer = next_layer
    return layer[0]


def build_merkle_proofs(leaf_hashes):
    """Return {leaf_hash: [{"hash": sibling, "left": bool}, ...]} for each leaf."""
    if not leaf_hashes:
        return {}

    leaves = sorted(leaf_hashes)
    proofs_by_index = [[] for _ in leaves]
    layer = [(leaf_hash, {index}) for index, leaf_hash in enumerate(leaves)]

    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        next_layer = []
        for index in range(0, len(layer), 2):
            left_hash, left_indices = layer[index]
            right_hash, right_indices = layer[index + 1]
            if left_hash == right_hash and left_indices == right_indices:
                for leaf_index in left_indices:
                    proofs_by_index[leaf_index].append({"hash": right_hash, "left": True})
            else:
                for leaf_index in left_indices:
                    proofs_by_index[leaf_index].append({"hash": right_hash, "left": True})
                for leaf_index in right_indices:
                    proofs_by_index[leaf_index].append({"hash": left_hash, "left": False})
            next_layer.append((_hash_pair(left_hash, right_hash), left_indices | right_indices))
        layer = next_layer

    proofs = {}
    for index, leaf_hash in enumerate(leaves):
        proofs.setdefault(leaf_hash, proofs_by_index[index])
    return proofs


def verify_merkle_proof(*, leaf_hash, proof, root):
    computed = leaf_hash
    for step in proof:
        sibling = step["hash"]
        if step["left"]:
            computed = _hash_pair(computed, sibling)
        else:
            computed = _hash_pair(sibling, computed)
    return computed == root


def get_reputation_events_for_period(*, period_start, period_end):
    return (
        ReputationEvent.objects.filter(
            created_at__gte=period_start,
            created_at__lte=period_end,
            event_type__in=REALIZED_EVENT_TYPES,
        )
        .select_related("prediction", "prediction__market", "user")
        .order_by("created_at", "id")
    )


def get_all_realized_reputation_events():
    """Every resolved/exited forecast that changed reputation points."""
    return (
        ReputationEvent.objects.filter(event_type__in=REALIZED_EVENT_TYPES)
        .select_related("prediction", "prediction__market", "user")
        .order_by("created_at", "id")
    )


def is_historical_batch(batch):
    return batch.batch_date == HISTORICAL_BATCH_DATE


def _batch_exists_for_date(batch_date):
    return AttestationBatch.objects.filter(batch_date=batch_date).exists()


def _previous_batch_root():
    previous = AttestationBatch.objects.order_by("-batch_date").first()
    return previous.merkle_root if previous else ""


def _sign_batch(*, merkle_root, record_count, period_start, period_end, prev_batch_root):
    message = {
        "version": 1,
        "merkle_root": merkle_root,
        "record_count": record_count,
        "period_start": _timestamp(period_start),
        "period_end": _timestamp(period_end),
        "prev_batch_root": prev_batch_root or ZERO_HASH,
        "score_version": SCORE_VERSION,
        "signer": _signer_id(),
        "chain_id": getattr(settings, "EAS_CHAIN_ID", 0),
    }
    signature = _sign(canonical_json(message))
    return message, signature


ZERO_HASH = "0x" + "0" * 64


def _create_attestation_batch(
    *,
    events,
    batch_date,
    period_start,
    period_end,
    prev_batch_root,
    force,
    log_label,
):
    records = [build_position_close_record(event) for event in events]
    leaf_hashes = [hash_position_close_record(record) for record in records]
    merkle_root = compute_merkle_root(leaf_hashes)
    message, signature = _sign_batch(
        merkle_root=merkle_root,
        record_count=len(records),
        period_start=period_start,
        period_end=period_end,
        prev_batch_root=prev_batch_root,
    )

    proofs = build_merkle_proofs(leaf_hashes)
    enriched_records = []
    for record, leaf_hash in zip(records, leaf_hashes, strict=True):
        enriched_records.append(
            {
                **record,
                "leaf_hash": leaf_hash,
                "merkle_proof": proofs.get(leaf_hash, []),
            }
        )

    chain_id = getattr(settings, "EAS_CHAIN_ID", 0)
    batch_kwargs = {
        "merkle_root": merkle_root,
        "batch_date": batch_date,
        "period_start": period_start,
        "period_end": period_end,
        "record_count": len(records),
        "records": enriched_records,
        "score_version": SCORE_VERSION,
        "prev_batch_root": prev_batch_root,
        "signer": _signer_id(),
        "signature": signature,
        "payload_hash": _hash_json(message),
        "status": AttestationBatch.Status.SIGNED,
        "chain_id": chain_id,
        "timestamped_at": timezone.now(),
    }

    try:
        with transaction.atomic():
            if force:
                AttestationBatch.objects.filter(batch_date=batch_date).delete()
            batch = AttestationBatch.objects.create(**batch_kwargs)
    except IntegrityError:
        batch = AttestationBatch.objects.get(merkle_root=merkle_root)
        return batch, False

    logger.info(
        "Built %s attestation batch root=%s records=%s period=%s→%s",
        log_label,
        batch.short_root,
        batch.record_count,
        period_start.isoformat(),
        period_end.isoformat(),
    )

    if getattr(settings, "EAS_ONCHAIN_ANCHOR_ENABLED", False):
        from integrations.eas_onchain import anchor_batch_onchain_safely

        batch = anchor_batch_onchain_safely(batch)

    return batch, True


def build_daily_attestation_batch(*, as_of=None, force=False):
    """
    Build a signed Merkle batch for the last 24 hours of realized reputation.

    Idempotent per UTC ``batch_date`` unless ``force=True``.
    """
    as_of = as_of or timezone.now()
    period_end = as_of
    period_start = as_of - timedelta(hours=24)
    batch_date = as_of.date()

    if not force and _batch_exists_for_date(batch_date):
        existing = AttestationBatch.objects.get(batch_date=batch_date)
        logger.info("Daily attestation batch already exists for %s", batch_date.isoformat())
        return existing, False

    events = list(get_reputation_events_for_period(period_start=period_start, period_end=period_end))
    prev_batch_root = _previous_batch_root() if not force else ""
    return _create_attestation_batch(
        events=events,
        batch_date=batch_date,
        period_start=period_start,
        period_end=period_end,
        prev_batch_root=prev_batch_root,
        force=force,
        log_label="daily",
    )


def build_historical_attestation_batch(*, force=False):
    """
    One-time genesis batch: every realized reputation position ever scored.

    Uses ``HISTORICAL_BATCH_DATE`` (1970-01-01) as a sentinel ``batch_date``.
    """
    if not force and _batch_exists_for_date(HISTORICAL_BATCH_DATE):
        existing = AttestationBatch.objects.get(batch_date=HISTORICAL_BATCH_DATE)
        logger.info("Historical attestation batch already exists")
        return existing, False

    events = list(get_all_realized_reputation_events())
    if events:
        period_start = events[0].created_at
        period_end = events[-1].created_at
    else:
        now = timezone.now()
        period_start = period_end = now

    return _create_attestation_batch(
        events=events,
        batch_date=HISTORICAL_BATCH_DATE,
        period_start=period_start,
        period_end=period_end,
        prev_batch_root="",
        force=force,
        log_label="historical",
    )


def verify_batch_signature(batch):
    message = {
        "version": 1,
        "merkle_root": batch.merkle_root,
        "record_count": batch.record_count,
        "period_start": _timestamp(batch.period_start),
        "period_end": _timestamp(batch.period_end),
        "prev_batch_root": batch.prev_batch_root or ZERO_HASH,
        "score_version": batch.score_version,
        "signer": _signer_id(),
        "chain_id": batch.chain_id,
    }
    expected = _sign(canonical_json(message))
    return expected == batch.signature and _hash_json(message) == batch.payload_hash


def get_batch_stats():
    from integrations.eas_onchain import get_anchor_wallet_address, onchain_ready

    latest = AttestationBatch.objects.order_by("-created_at").first()
    total_records = sum(
        AttestationBatch.objects.values_list("record_count", flat=True)[:365]
    )
    anchor_wallet = get_anchor_wallet_address()
    return {
        "latest_batch": latest,
        "total_batches": AttestationBatch.objects.count(),
        "total_records_anchored": total_records,
        "chain_id": getattr(settings, "EAS_CHAIN_ID", 0),
        "onchain_enabled": onchain_ready(),
        "onchain_configured": bool(getattr(settings, "EAS_ONCHAIN_ANCHOR_ENABLED", False)),
        "anchor_wallet": anchor_wallet,
        "anchor_wallet_basescan": (
            f"https://basescan.org/address/{anchor_wallet}" if anchor_wallet else ""
        ),
    }
