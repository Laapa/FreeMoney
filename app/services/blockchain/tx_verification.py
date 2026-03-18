from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import urlopen

from app.services.blockchain.options import SupportedCryptoOption

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55aeb"


class BlockchainVerificationReason(str, Enum):
    TX_NOT_FOUND = "tx_not_found"
    TX_FAILED = "tx_failed"
    NETWORK_MISMATCH = "network_mismatch"
    RECIPIENT_MISMATCH = "recipient_mismatch"
    TOKEN_MISMATCH = "token_mismatch"
    AMOUNT_TOO_LOW = "amount_too_low"
    UNSUPPORTED_NETWORK = "unsupported_network"
    PROVIDER_ERROR = "provider_error"


@dataclass(frozen=True)
class BlockchainVerificationSuccess:
    tx_hash: str
    network: str
    token: str | None
    amount: Decimal
    recipient: str
    raw_reference: str


@dataclass(frozen=True)
class BlockchainVerificationResult:
    ok: bool
    reason: BlockchainVerificationReason | None = None
    note: str | None = None
    data: BlockchainVerificationSuccess | None = None


class EvmExplorerClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        fetcher: Callable[[str], dict[str, Any]] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._fetcher = fetcher or self._default_fetcher

    def get_transaction(self, tx_hash: str) -> dict[str, Any] | None:
        payload = self._call({"module": "proxy", "action": "eth_getTransactionByHash", "txhash": tx_hash})
        return payload.get("result")

    def get_receipt(self, tx_hash: str) -> dict[str, Any] | None:
        payload = self._call({"module": "proxy", "action": "eth_getTransactionReceipt", "txhash": tx_hash})
        return payload.get("result")

    def _call(self, params: dict[str, str]) -> dict[str, Any]:
        query = params.copy()
        if self._api_key:
            query["apikey"] = self._api_key
        url = f"{self._base_url}?{urlencode(query)}"
        return self._fetcher(url)

    @staticmethod
    def _default_fetcher(url: str) -> dict[str, Any]:
        with urlopen(url, timeout=20) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))


class EvmTxVerifier:
    def __init__(
        self,
        *,
        explorer_urls: dict[str, str],
        crypto_options: dict[str, SupportedCryptoOption],
        explorer_api_keys: dict[str, str] | None = None,
        amount_tolerance: Decimal = Decimal("0"),
        client_factory: Callable[..., EvmExplorerClient] | None = None,
    ) -> None:
        self._explorer_urls = {k.lower(): v for k, v in explorer_urls.items()}
        self._crypto_options = crypto_options
        self._explorer_api_keys = {k.lower(): v for k, v in (explorer_api_keys or {}).items()}
        self._amount_tolerance = amount_tolerance
        self._client_factory = client_factory or EvmExplorerClient

    def verify_transfer(
        self,
        *,
        tx_hash: str,
        expected_network: str,
        expected_amount: Decimal,
        expected_token_symbol: str | None = None,
    ) -> BlockchainVerificationResult:
        network = (expected_network or "").strip().lower()
        if network not in self._explorer_urls:
            return BlockchainVerificationResult(
                ok=False,
                reason=BlockchainVerificationReason.UNSUPPORTED_NETWORK,
                note=f"Unsupported network: {expected_network}",
            )

        option = _find_option(
            options=self._crypto_options,
            network=network,
            token_symbol=expected_token_symbol,
        )
        if option is None:
            return BlockchainVerificationResult(
                ok=False,
                reason=BlockchainVerificationReason.TOKEN_MISMATCH,
                note=f"Unsupported network/token option: {network}/{expected_token_symbol or '-'}",
            )
        recipient = _normalize_address(option.recipient_wallet)
        if not recipient:
            return BlockchainVerificationResult(
                ok=False,
                reason=BlockchainVerificationReason.NETWORK_MISMATCH,
                note=f"Recipient wallet is not configured for option {option.key}",
            )

        client = self._client_factory(
            base_url=self._explorer_urls[network],
            api_key=self._explorer_api_keys.get(network),
        )

        try:
            tx = client.get_transaction(tx_hash)
            receipt = client.get_receipt(tx_hash)
        except Exception as exc:
            return BlockchainVerificationResult(
                ok=False,
                reason=BlockchainVerificationReason.PROVIDER_ERROR,
                note=f"Explorer provider error: {exc}",
            )

        if tx is None or receipt is None:
            return BlockchainVerificationResult(
                ok=False,
                reason=BlockchainVerificationReason.TX_NOT_FOUND,
                note="Transaction was not found on explorer",
            )

        status_hex = (receipt.get("status") or "").lower()
        if status_hex != "0x1":
            return BlockchainVerificationResult(
                ok=False,
                reason=BlockchainVerificationReason.TX_FAILED,
                note=f"Transaction receipt status is {status_hex or 'unknown'}",
            )

        transfer = _extract_transfer(tx=tx, receipt=receipt, option=option)
        if transfer is None:
            return BlockchainVerificationResult(
                ok=False,
                reason=BlockchainVerificationReason.TOKEN_MISMATCH,
                note="Expected token transfer was not found in transaction logs",
            )

        actual_recipient = _normalize_address(transfer["recipient"])
        if actual_recipient != recipient:
            return BlockchainVerificationResult(
                ok=False,
                reason=BlockchainVerificationReason.RECIPIENT_MISMATCH,
                note=f"Unexpected recipient wallet: {actual_recipient}",
            )

        actual_amount = transfer["amount"]
        if actual_amount + self._amount_tolerance < expected_amount:
            return BlockchainVerificationResult(
                ok=False,
                reason=BlockchainVerificationReason.AMOUNT_TOO_LOW,
                note=f"Transaction amount {actual_amount} is lower than expected {expected_amount}",
            )

        return BlockchainVerificationResult(
            ok=True,
            note="Verified on-chain",
            data=BlockchainVerificationSuccess(
                tx_hash=tx_hash,
                network=network,
                token=option.token_symbol,
                amount=actual_amount,
                recipient=actual_recipient,
                raw_reference=f"explorer:{self._explorer_urls[network]}",
            ),
        )


def _extract_transfer(*, tx: dict[str, Any], receipt: dict[str, Any], option: SupportedCryptoOption) -> dict[str, Any] | None:
    if not option.is_native_coin:
        expected_token_contract = _normalize_address(option.token_contract)
        if not expected_token_contract:
            return None
        logs = receipt.get("logs") or []
        for log in logs:
            if _normalize_address(log.get("address")) != expected_token_contract:
                continue
            topics = log.get("topics") or []
            if len(topics) < 3:
                continue
            if not str(topics[0]).lower().startswith(TRANSFER_TOPIC):
                continue
            recipient = _topic_to_address(topics[2])
            amount = _hex_to_decimal(log.get("data"), decimals=option.token_decimals)
            return {"recipient": recipient, "amount": amount}
        return None

    return {
        "recipient": tx.get("to"),
        "amount": _hex_to_decimal(tx.get("value"), decimals=18),
    }


def _find_option(
    *,
    options: dict[str, SupportedCryptoOption],
    network: str,
    token_symbol: str | None,
) -> SupportedCryptoOption | None:
    normalized_token_symbol = _normalize_token(token_symbol)
    for option in options.values():
        if option.network != network:
            continue
        if option.token_symbol != normalized_token_symbol:
            continue
        return option
    return None


def _topic_to_address(topic: str | None) -> str:
    if not topic:
        return ""
    clean = topic.lower().removeprefix("0x")
    return _normalize_address(f"0x{clean[-40:]}")


def _hex_to_decimal(value: str | None, *, decimals: int) -> Decimal:
    if not value:
        return Decimal("0")
    return Decimal(int(value, 16)) / (Decimal(10) ** decimals)


def _normalize_address(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().lower()


def _normalize_token(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    return normalized
