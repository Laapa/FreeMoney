from decimal import Decimal

from app.services.blockchain.tx_verification import (
    BlockchainVerificationReason,
    EvmExplorerClient,
    EvmTxVerifier,
)


def _build_client_factory(transactions: dict[str, dict], receipts: dict[str, dict]):
    class _Client(EvmExplorerClient):
        def __init__(self, *, base_url: str, api_key: str | None = None) -> None:
            super().__init__(base_url=base_url, api_key=api_key, fetcher=lambda _url: {})

        def get_transaction(self, tx_hash: str) -> dict | None:
            return transactions.get(tx_hash)

        def get_receipt(self, tx_hash: str) -> dict | None:
            return receipts.get(tx_hash)

    return _Client


def test_verify_native_success_path() -> None:
    tx_hash = "0xabc"
    verifier = EvmTxVerifier(
        explorer_urls={"bsc": "https://api.bscscan.com/api"},
        recipient_wallets={"bsc": "0xrecipient"},
        client_factory=_build_client_factory(
            transactions={tx_hash: {"to": "0xRecipient", "value": hex(25 * 10**18)}},
            receipts={tx_hash: {"status": "0x1", "logs": []}},
        ),
    )

    result = verifier.verify_transfer(
        tx_hash=tx_hash,
        expected_network="bsc",
        expected_amount=Decimal("25"),
    )

    assert result.ok is True
    assert result.data is not None
    assert result.data.amount == Decimal("25")
    assert result.data.recipient == "0xrecipient"


def test_verify_fails_for_wrong_recipient() -> None:
    tx_hash = "0xdef"
    verifier = EvmTxVerifier(
        explorer_urls={"bsc": "https://api.bscscan.com/api"},
        recipient_wallets={"bsc": "0xrecipient"},
        client_factory=_build_client_factory(
            transactions={tx_hash: {"to": "0xsomeoneelse", "value": hex(25 * 10**18)}},
            receipts={tx_hash: {"status": "0x1", "logs": []}},
        ),
    )

    result = verifier.verify_transfer(tx_hash=tx_hash, expected_network="bsc", expected_amount=Decimal("25"))

    assert result.ok is False
    assert result.reason == BlockchainVerificationReason.RECIPIENT_MISMATCH


def test_verify_fails_for_wrong_amount() -> None:
    tx_hash = "0x987"
    verifier = EvmTxVerifier(
        explorer_urls={"bsc": "https://api.bscscan.com/api"},
        recipient_wallets={"bsc": "0xrecipient"},
        client_factory=_build_client_factory(
            transactions={tx_hash: {"to": "0xrecipient", "value": hex(10 * 10**18)}},
            receipts={tx_hash: {"status": "0x1", "logs": []}},
        ),
    )

    result = verifier.verify_transfer(tx_hash=tx_hash, expected_network="bsc", expected_amount=Decimal("25"))

    assert result.ok is False
    assert result.reason == BlockchainVerificationReason.AMOUNT_TOO_LOW


def test_verify_fails_for_wrong_status() -> None:
    tx_hash = "0x654"
    verifier = EvmTxVerifier(
        explorer_urls={"bsc": "https://api.bscscan.com/api"},
        recipient_wallets={"bsc": "0xrecipient"},
        client_factory=_build_client_factory(
            transactions={tx_hash: {"to": "0xrecipient", "value": hex(25 * 10**18)}},
            receipts={tx_hash: {"status": "0x0", "logs": []}},
        ),
    )

    result = verifier.verify_transfer(tx_hash=tx_hash, expected_network="bsc", expected_amount=Decimal("25"))

    assert result.ok is False
    assert result.reason == BlockchainVerificationReason.TX_FAILED
