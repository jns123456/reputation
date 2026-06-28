"""Wallet address validation for contest payout requests by blockchain."""

from __future__ import annotations

import re

from web3 import Web3

from reputation.models import ContestPayoutRequest

_TRON_ADDRESS_RE = re.compile(r"^T[1-9A-HJ-NP-Za-km-z]{33}$")
_SOLANA_ADDRESS_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")

_EVM_CHAINS = frozenset(
    {
        ContestPayoutRequest.Chain.ETHEREUM,
        ContestPayoutRequest.Chain.BASE,
        ContestPayoutRequest.Chain.POLYGON,
        ContestPayoutRequest.Chain.BSC,
        ContestPayoutRequest.Chain.ARBITRUM,
        ContestPayoutRequest.Chain.OPTIMISM,
    }
)


class InvalidPayoutAddressError(ValueError):
    pass


def normalize_payout_chain(chain: str) -> str:
    normalized = (chain or "").strip().lower()
    valid = {value for value, _label in ContestPayoutRequest.Chain.choices}
    if normalized not in valid:
        raise InvalidPayoutAddressError("unsupported chain")
    return normalized


def validate_payout_wallet_address(*, chain: str, address: str) -> str:
    """Return a normalized wallet address for the selected payout network."""
    chain = normalize_payout_chain(chain)
    raw = (address or "").strip()
    if not raw:
        raise InvalidPayoutAddressError("empty address")

    if chain in _EVM_CHAINS:
        if not Web3.is_address(raw):
            raise InvalidPayoutAddressError("invalid evm address")
        return Web3.to_checksum_address(raw)

    if chain == ContestPayoutRequest.Chain.TRON:
        if not _TRON_ADDRESS_RE.fullmatch(raw):
            raise InvalidPayoutAddressError("invalid tron address")
        return raw

    if chain == ContestPayoutRequest.Chain.SOLANA:
        if not _SOLANA_ADDRESS_RE.fullmatch(raw):
            raise InvalidPayoutAddressError("invalid solana address")
        return raw

    raise InvalidPayoutAddressError("unsupported chain")
