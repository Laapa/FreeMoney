from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from urllib import error, parse, request


class CryptoPayClientError(Exception):
    """Raised when Crypto Pay request fails."""


@dataclass(frozen=True, slots=True)
class CryptoPayInvoice:
    invoice_id: str
    status: str
    amount: Decimal
    pay_url: str | None = None
    bot_invoice_url: str | None = None
    expires_at: datetime | None = None


class CryptoPayClient:
    def __init__(self, *, api_token: str, base_url: str, timeout_seconds: float = 10.0) -> None:
        self._api_token = api_token
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def get_me(self) -> dict[str, Any]:
        result = self._request("GET", "/getMe")
        if not isinstance(result, dict):
            raise CryptoPayClientError("Crypto Pay getMe response format is invalid.")
        return result

    def create_invoice(self, *, amount: Decimal, asset: str, expires_in: int) -> CryptoPayInvoice:
        payload = {
            "amount": str(amount),
            "asset": asset,
            "expires_in": expires_in,
            "allow_comments": False,
            "allow_anonymous": False,
        }
        result = self._request("POST", "/createInvoice", payload)
        if not isinstance(result, dict):
            raise CryptoPayClientError("Crypto Pay createInvoice response format is invalid.")
        return _parse_invoice(result)

    def get_invoices(self, *, invoice_ids: list[str] | None = None) -> list[CryptoPayInvoice]:
        query = ""
        if invoice_ids:
            query = "?" + parse.urlencode({"invoice_ids": ",".join(invoice_ids)})
        result = self._request("GET", f"/getInvoices{query}")
        items = result.get("items") if isinstance(result, dict) else None
        if not isinstance(items, list):
            raise CryptoPayClientError("Crypto Pay getInvoices response format is invalid.")
        return [_parse_invoice(item) for item in items if isinstance(item, dict)]

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any] | list[Any]:
        url = f"{self._base_url}{path}"
        body: bytes | None = None
        headers = {
    "Crypto-Pay-API-Token": self._api_token,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
                  }
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = request.Request(url, data=body, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=self._timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else ""
            raise CryptoPayClientError(f"Crypto Pay returned HTTP {exc.code}: {details}") from exc
        except (error.URLError, TimeoutError) as exc:
            raise CryptoPayClientError("Crypto Pay is temporarily unavailable. Please retry shortly.") from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CryptoPayClientError("Crypto Pay response format is invalid.") from exc

        if not isinstance(data, dict):
            raise CryptoPayClientError("Crypto Pay response format is invalid.")
        if data.get("ok") is not True:
            err = data.get("error") or data.get("message") or "Unknown Crypto Pay error"
            raise CryptoPayClientError(str(err))

        result = data.get("result")
        if not isinstance(result, (dict, list)):
            raise CryptoPayClientError("Crypto Pay result format is invalid.")
        return result


def _parse_invoice(raw: dict[str, Any]) -> CryptoPayInvoice:
    raw_invoice_id = raw.get("invoice_id")
    raw_status = raw.get("status")
    raw_amount = raw.get("amount")

    if raw_invoice_id is None or raw_status is None or raw_amount is None:
        raise CryptoPayClientError("Crypto Pay invoice payload is missing required fields.")

    expires_at: datetime | None = None
    raw_expires_at = raw.get("expiration_date")
    if isinstance(raw_expires_at, str):
        try:
            expires_at = datetime.fromisoformat(raw_expires_at.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            expires_at = None

    return CryptoPayInvoice(
        invoice_id=str(raw_invoice_id),
        status=str(raw_status),
        amount=Decimal(str(raw_amount)),
        pay_url=str(raw.get("pay_url")) if raw.get("pay_url") else None,
        bot_invoice_url=str(raw.get("bot_invoice_url")) if raw.get("bot_invoice_url") else None,
        expires_at=expires_at,
    )
