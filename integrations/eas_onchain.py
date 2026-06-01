"""Submit daily batch anchors to EAS on Base."""

from __future__ import annotations

import logging

from django.conf import settings
from django.utils import timezone
from eth_abi import encode as abi_encode
from eth_account import Account
from web3 import Web3
from web3.exceptions import ContractLogicError

from integrations.attestation_services import SCHEMA_DEFINITIONS, get_or_create_attestation_schema
from integrations.models import AttestationBatch, AttestationSchema

logger = logging.getLogger(__name__)

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
ZERO_BYTES32 = "0x" + "0" * 64
NO_EXPIRATION = 0

BASE_CHAIN_ID = 8453
DEFAULT_EAS_ADDRESS = "0x4200000000000000000000000000000000000021"
DEFAULT_SCHEMA_REGISTRY_ADDRESS = "0x4200000000000000000000000000000000000020"

SCHEMA_REGISTRY_ABI = [
    {
        "inputs": [
            {"internalType": "string", "name": "schema", "type": "string"},
            {"internalType": "address", "name": "resolver", "type": "address"},
            {"internalType": "bool", "name": "revocable", "type": "bool"},
        ],
        "name": "register",
        "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "bytes32", "name": "uid", "type": "bytes32"}],
        "name": "getSchema",
        "outputs": [
            {"internalType": "bytes32", "name": "uid", "type": "bytes32"},
            {"internalType": "address", "name": "resolver", "type": "address"},
            {"internalType": "bool", "name": "revocable", "type": "bool"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]

EAS_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "bytes32", "name": "schema", "type": "bytes32"},
                    {
                        "components": [
                            {"internalType": "address", "name": "recipient", "type": "address"},
                            {"internalType": "uint64", "name": "expirationTime", "type": "uint64"},
                            {"internalType": "bool", "name": "revocable", "type": "bool"},
                            {"internalType": "bytes32", "name": "refUID", "type": "bytes32"},
                            {"internalType": "bytes", "name": "data", "type": "bytes"},
                            {"internalType": "uint256", "name": "value", "type": "uint256"},
                        ],
                        "internalType": "struct AttestationRequestData",
                        "name": "data",
                        "type": "tuple",
                    },
                ],
                "internalType": "struct AttestationRequest",
                "name": "request",
                "type": "tuple",
            }
        ],
        "name": "attest",
        "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "recipient", "type": "address"},
            {"indexed": True, "internalType": "address", "name": "attester", "type": "address"},
            {"indexed": True, "internalType": "bytes32", "name": "uid", "type": "bytes32"},
            {"indexed": True, "internalType": "bytes32", "name": "schemaUID", "type": "bytes32"},
        ],
        "name": "Attested",
        "type": "event",
    },
]


def _hex_to_bytes32(value):
    cleaned = (value or ZERO_BYTES32).removeprefix("0x").lower().rjust(64, "0")[-64:]
    return bytes.fromhex(cleaned)


def compute_schema_uid(*, schema, resolver=ZERO_ADDRESS, revocable=True):
    """Match EAS SchemaRegistry.getSchemaUID(schema, resolver, revocable)."""
    schema_hash = Web3.keccak(text=schema)
    resolver_bytes = bytes.fromhex(Web3.to_checksum_address(resolver)[2:])
    revocable_byte = b"\x01" if revocable else b"\x00"
    return Web3.keccak(schema_hash + resolver_bytes + revocable_byte)


def get_daily_batch_schema_string():
    return SCHEMA_DEFINITIONS[AttestationSchema.Kind.DAILY_BATCH_ANCHOR]["schema"]


def onchain_ready():
    return bool(
        getattr(settings, "EAS_ONCHAIN_ANCHOR_ENABLED", False)
        and getattr(settings, "EAS_ANCHOR_PRIVATE_KEY", "")
        and getattr(settings, "EAS_CHAIN_ID", 0) == BASE_CHAIN_ID
    )


def get_anchor_wallet_address():
    configured = getattr(settings, "EAS_ANCHOR_WALLET_ADDRESS", "") or ""
    if configured:
        return Web3.to_checksum_address(configured)
    private_key = getattr(settings, "EAS_ANCHOR_PRIVATE_KEY", "") or ""
    if private_key:
        return Account.from_key(private_key).address
    return ""


def _get_web3():
    rpc_url = getattr(settings, "EAS_BASE_RPC_URL", "https://mainnet.base.org")
    web3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 30}))
    if not web3.is_connected():
        raise ConnectionError(f"Unable to connect to Base RPC at {rpc_url}")
    return web3


def _get_account():
    private_key = getattr(settings, "EAS_ANCHOR_PRIVATE_KEY", "")
    if not private_key:
        raise ValueError("EAS_ANCHOR_PRIVATE_KEY is not configured")
    account = Account.from_key(private_key)
    expected = getattr(settings, "EAS_ANCHOR_WALLET_ADDRESS", "")
    if expected and account.address.lower() != Web3.to_checksum_address(expected).lower():
        raise ValueError("EAS_ANCHOR_PRIVATE_KEY does not match EAS_ANCHOR_WALLET_ADDRESS")
    return account


def encode_daily_batch_payload(batch):
    prev_root = batch.prev_batch_root or ZERO_BYTES32
    return abi_encode(
        ["bytes32", "uint32", "uint64", "uint64", "uint16", "bytes32"],
        [
            _hex_to_bytes32(batch.merkle_root),
            batch.record_count,
            int(batch.period_start.timestamp()),
            int(batch.period_end.timestamp()),
            batch.score_version,
            _hex_to_bytes32(prev_root),
        ],
    )


def ensure_daily_batch_schema_registered(*, web3=None, account=None):
    """Register the daily batch schema on Base if needed; persist UID locally."""
    schema_row = get_or_create_attestation_schema(AttestationSchema.Kind.DAILY_BATCH_ANCHOR)
    schema_string = get_daily_batch_schema_string()
    schema_uid = compute_schema_uid(schema=schema_string, resolver=ZERO_ADDRESS, revocable=True)
    schema_uid_hex = Web3.to_hex(schema_uid)

    if schema_row.schema_uid != schema_uid_hex or schema_row.chain_id != BASE_CHAIN_ID:
        schema_row.schema_uid = schema_uid_hex
        schema_row.chain_id = BASE_CHAIN_ID
        schema_row.verifying_contract = getattr(
            settings, "EAS_CONTRACT_ADDRESS", DEFAULT_EAS_ADDRESS
        )
        schema_row.save(
            update_fields=["schema_uid", "chain_id", "verifying_contract", "updated_at"]
        )

    if not onchain_ready():
        return schema_uid_hex

    web3 = web3 or _get_web3()
    account = account or _get_account()
    registry = web3.eth.contract(
        address=Web3.to_checksum_address(
            getattr(settings, "EAS_SCHEMA_REGISTRY_ADDRESS", DEFAULT_SCHEMA_REGISTRY_ADDRESS)
        ),
        abi=SCHEMA_REGISTRY_ABI,
    )
    try:
        existing = registry.functions.getSchema(schema_uid).call()
        if existing[0] != b"\x00" * 32:
            return schema_uid_hex
    except ContractLogicError:
        pass

    tx = registry.functions.register(schema_string, ZERO_ADDRESS, True).build_transaction(
        {
            "from": account.address,
            "nonce": web3.eth.get_transaction_count(account.address),
            "chainId": BASE_CHAIN_ID,
        }
    )
    tx_hash = _send_transaction(web3, account, tx)
    logger.info("Registered EAS daily batch schema on Base: %s tx=%s", schema_uid_hex, tx_hash)
    return schema_uid_hex


def anchor_batch_onchain(batch):
    """Attest the batch Merkle root on Base via EAS."""
    if batch.status == AttestationBatch.Status.ANCHORED and batch.transaction_hash:
        return batch

    if not onchain_ready():
        raise ValueError("On-chain anchoring is not fully configured")

    web3 = _get_web3()
    account = _get_account()
    schema_uid_hex = ensure_daily_batch_schema_registered(web3=web3, account=account)
    schema_uid = bytes.fromhex(schema_uid_hex.removeprefix("0x"))

    eas = web3.eth.contract(
        address=Web3.to_checksum_address(
            getattr(settings, "EAS_CONTRACT_ADDRESS", DEFAULT_EAS_ADDRESS)
        ),
        abi=EAS_ABI,
    )
    encoded_data = encode_daily_batch_payload(batch)
    request = (
        schema_uid,
        (
            account.address,
            NO_EXPIRATION,
            True,
            bytes.fromhex(ZERO_BYTES32[2:]),
            encoded_data,
            0,
        ),
    )
    tx = eas.functions.attest(request).build_transaction(
        {
            "from": account.address,
            "nonce": web3.eth.get_transaction_count(account.address),
            "chainId": BASE_CHAIN_ID,
            "value": 0,
        }
    )
    tx_hash = _send_transaction(web3, account, tx)
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
    attestation_uid = _extract_attestation_uid(web3, receipt)

    batch.transaction_hash = tx_hash
    batch.on_chain_uid = attestation_uid or ""
    batch.status = AttestationBatch.Status.ANCHORED
    batch.chain_id = BASE_CHAIN_ID
    batch.timestamped_at = timezone.now()
    batch.save(
        update_fields=[
            "transaction_hash",
            "on_chain_uid",
            "status",
            "chain_id",
            "timestamped_at",
            "updated_at",
        ]
    )
    logger.info(
        "Anchored daily batch on Base: root=%s tx=%s uid=%s",
        batch.short_root,
        tx_hash,
        attestation_uid,
    )
    return batch


def _send_transaction(web3, account, tx):
    latest = web3.eth.get_block("latest")
    base_fee = latest.get("baseFeePerGas") or web3.to_wei(0.01, "gwei")
    priority = web3.to_wei(0.001, "gwei")
    tx["gas"] = web3.eth.estimate_gas(tx)
    tx["maxFeePerGas"] = base_fee + priority
    tx["maxPriorityFeePerGas"] = priority
    signed = account.sign_transaction(tx)
    return web3.eth.send_raw_transaction(signed.raw_transaction).hex()


def _extract_attestation_uid(web3, receipt):
    eas = web3.eth.contract(
        address=Web3.to_checksum_address(
            getattr(settings, "EAS_CONTRACT_ADDRESS", DEFAULT_EAS_ADDRESS)
        ),
        abi=EAS_ABI,
    )
    for log in receipt.logs:
        if log["address"].lower() != eas.address.lower():
            continue
        try:
            decoded = eas.events.Attested().process_log(log)
            return Web3.to_hex(decoded["args"]["uid"])
        except Exception:
            continue
    return ""


def anchor_batch_onchain_safely(batch):
    try:
        return anchor_batch_onchain(batch)
    except Exception:
        logger.exception("Failed to anchor batch %s on Base", batch.merkle_root)
        batch.status = AttestationBatch.Status.FAILED
        batch.save(update_fields=["status", "updated_at"])
        return batch
