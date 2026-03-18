from decimal import Decimal

from app.services.blockchain.tx_verification import (
    BlockchainVerificationReason,
    EvmExplorerClient,
    EvmTxVerifier,
)
from app.services.blockchain.options import SupportedCryptoOption


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
    option = SupportedCryptoOption(
        key="bnb_bsc",
        network="bsc",
        display_label="BNB BSC",
        token_symbol=None,
        token_contract=None,
        token_decimals=18,
        recipient_wallet="0x00000000000000000000000000000000000000aa",
        is_native_coin=True,
    )
    verifier = EvmTxVerifier(
        explorer_urls={"bsc": "https://api.bscscan.com/api"},
        crypto_options={option.key: option},
        client_factory=_build_client_factory(
            transactions={tx_hash: {"to": "0x00000000000000000000000000000000000000aa", "value": hex(25 * 10**18)}},
            receipts={tx_hash: {"status": "0x1", "logs": []}},
        ),
    )

    result = verifier.verify_transfer(
        tx_hash=tx_hash,
        expected_network="bsc",
        expected_amount=Decimal("25"),
        expected_token_symbol=None,
    )

    assert result.ok is True
    assert result.data is not None
    assert result.data.amount == Decimal("25")
    assert result.data.recipient == "0x00000000000000000000000000000000000000aa"


def test_verify_fails_for_wrong_recipient() -> None:
    tx_hash = "0xdef"
    option = SupportedCryptoOption(
        key="bnb_bsc",
        network="bsc",
        display_label="BNB BSC",
        token_symbol=None,
        token_contract=None,
        token_decimals=18,
        recipient_wallet="0x00000000000000000000000000000000000000aa",
        is_native_coin=True,
    )
    verifier = EvmTxVerifier(
        explorer_urls={"bsc": "https://api.bscscan.com/api"},
        crypto_options={option.key: option},
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
    token_contract = "0x55d398326f99059ff775485246999027b3197955"
    option = SupportedCryptoOption(
        key="usdt_bsc",
        network="bsc",
        display_label="USDT BSC",
        token_symbol="usdt",
        token_contract=token_contract,
        token_decimals=6,
        recipient_wallet="0x00000000000000000000000000000000000000aa",
        is_native_coin=False,
    )
    verifier = EvmTxVerifier(
        explorer_urls={"bsc": "https://api.bscscan.com/api"},
        crypto_options={option.key: option},
        client_factory=_build_client_factory(
            transactions={tx_hash: {"to": "0x00000000000000000000000000000000000000aa", "value": "0x0"}},
            receipts={
                tx_hash: {
                    "status": "0x1",
                    "logs": [
                        {
                            "address": token_contract,
                            "topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55aeb", "0x0", "0x00000000000000000000000000000000000000aa"],
                            "data": hex(10 * 10**6),
                        }
                    ],
                }
            },
        ),
    )

    result = verifier.verify_transfer(
        tx_hash=tx_hash,
        expected_network="bsc",
        expected_amount=Decimal("25"),
        expected_token_symbol="usdt",
    )

    assert result.ok is False
    assert result.reason == BlockchainVerificationReason.AMOUNT_TOO_LOW


def test_verify_fails_for_wrong_status() -> None:
    tx_hash = "0x654"
    option = SupportedCryptoOption(
        key="bnb_bsc",
        network="bsc",
        display_label="BNB BSC",
        token_symbol=None,
        token_contract=None,
        token_decimals=18,
        recipient_wallet="0x00000000000000000000000000000000000000aa",
        is_native_coin=True,
    )
    verifier = EvmTxVerifier(
        explorer_urls={"bsc": "https://api.bscscan.com/api"},
        crypto_options={option.key: option},
        client_factory=_build_client_factory(
            transactions={tx_hash: {"to": "0x00000000000000000000000000000000000000aa", "value": hex(25 * 10**18)}},
            receipts={tx_hash: {"status": "0x0", "logs": []}},
        ),
    )

    result = verifier.verify_transfer(tx_hash=tx_hash, expected_network="bsc", expected_amount=Decimal("25"))

    assert result.ok is False
    assert result.reason == BlockchainVerificationReason.TX_FAILED


def test_verify_bsc_usdt_token_success() -> None:
    tx_hash = "0x222"
    token_contract = "0x55d398326f99059ff775485246999027b3197955"
    option = SupportedCryptoOption(
        key="usdt_bsc",
        network="bsc",
        display_label="USDT BSC",
        token_symbol="usdt",
        token_contract=token_contract,
        token_decimals=6,
        recipient_wallet="0x00000000000000000000000000000000000000aa",
        is_native_coin=False,
    )
    verifier = EvmTxVerifier(
        explorer_urls={"bsc": "https://api.bscscan.com/api"},
        crypto_options={option.key: option},
        client_factory=_build_client_factory(
            transactions={tx_hash: {"to": "0xrouter", "value": "0x0"}},
            receipts={
                tx_hash: {
                    "status": "0x1",
                    "logs": [
                        {
                            "address": token_contract,
                            "topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55aeb", "0x0", "0x00000000000000000000000000000000000000aa"],
                            "data": hex(25_500_000),
                        }
                    ],
                }
            },
        ),
    )

    result = verifier.verify_transfer(
        tx_hash=tx_hash,
        expected_network="bsc",
        expected_amount=Decimal("25"),
        expected_token_symbol="usdt",
    )

    assert result.ok is True
    assert result.data is not None
    assert result.data.amount == Decimal("25.5")


def test_verify_fails_for_token_contract_mismatch() -> None:
    tx_hash = "0x333"
    option = SupportedCryptoOption(
        key="usdt_bsc",
        network="bsc",
        display_label="USDT BSC",
        token_symbol="usdt",
        token_contract="0x55d398326f99059ff775485246999027b3197955",
        token_decimals=18,
        recipient_wallet="0x00000000000000000000000000000000000000aa",
        is_native_coin=False,
    )
    verifier = EvmTxVerifier(
        explorer_urls={"bsc": "https://api.bscscan.com/api"},
        crypto_options={option.key: option},
        client_factory=_build_client_factory(
            transactions={tx_hash: {"to": "0xrouter", "value": "0x0"}},
            receipts={
                tx_hash: {
                    "status": "0x1",
                    "logs": [
                        {
                            "address": "0x1111111111111111111111111111111111111111",
                            "topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55aeb", "0x0", "0x00000000000000000000000000000000000000aa"],
                            "data": hex(25 * 10**18),
                        }
                    ],
                }
            },
        ),
    )

    result = verifier.verify_transfer(
        tx_hash=tx_hash,
        expected_network="bsc",
        expected_amount=Decimal("25"),
        expected_token_symbol="usdt",
    )

    assert result.ok is False
    assert result.reason == BlockchainVerificationReason.TOKEN_MISMATCH
