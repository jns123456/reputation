"""Wallet address validation for contest payouts."""

from django.test import TestCase

from reputation.models import ContestPayoutRequest
from reputation.payout_address_validation import (
    InvalidPayoutAddressError,
    validate_payout_wallet_address,
)

VALID_EVM = "0x" + "AbCdEf0123456789AbCdEf0123456789AbCdEf01"
VALID_TRON = "T" + "9" * 33
VALID_SOLANA = "7EcDhSYGxfxqJqJqJqJqJqJqJqJqJqJqJqJqJqJqJq"


class PayoutAddressValidationTests(TestCase):
    def test_evm_address_is_checksum_normalized(self):
        raw = "0xabcdef0123456789abcdef0123456789abcdef01"
        normalized = validate_payout_wallet_address(
            chain=ContestPayoutRequest.Chain.BASE,
            address=raw,
        )
        self.assertTrue(normalized.startswith("0x"))
        self.assertNotEqual(normalized, raw)

    def test_rejects_invalid_evm_address(self):
        with self.assertRaises(InvalidPayoutAddressError):
            validate_payout_wallet_address(
                chain=ContestPayoutRequest.Chain.ETHEREUM,
                address="0x123",
            )

    def test_accepts_tron_address(self):
        normalized = validate_payout_wallet_address(
            chain=ContestPayoutRequest.Chain.TRON,
            address=VALID_TRON,
        )
        self.assertEqual(normalized, VALID_TRON)

    def test_rejects_tron_on_evm_chain(self):
        with self.assertRaises(InvalidPayoutAddressError):
            validate_payout_wallet_address(
                chain=ContestPayoutRequest.Chain.POLYGON,
                address=VALID_TRON,
            )

    def test_accepts_solana_address(self):
        normalized = validate_payout_wallet_address(
            chain=ContestPayoutRequest.Chain.SOLANA,
            address=VALID_SOLANA,
        )
        self.assertEqual(normalized, VALID_SOLANA)

    def test_rejects_unsupported_chain(self):
        with self.assertRaises(InvalidPayoutAddressError):
            validate_payout_wallet_address(chain="unknown", address=VALID_EVM)
