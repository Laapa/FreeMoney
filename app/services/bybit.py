from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
from decimal import Decimal
from typing import Any
from urllib import error, parse, request


class BybitClientError(Exception):
    pass


@dataclass(frozen=True)
class BybitInternalDepositRecord:
    tx_id: str | None
    amount: Decimal
    coin: str
    status: str
    from_member_id: str | None
    created_time_ms: int
    raw: dict[str, Any]


@dataclass(frozen=True)
class BybitInternalDepositResult:
    records: list[BybitInternalDepositRecord]
    next_cursor: str | None


class BybitClient:
    def __init__(
        self,
        *,
        api_key: str,
        api_secret: str,
        base_url: str = "https://api.bybit.com",
        recv_window: int = 5000,
        timeout_seconds: float = 10.0,
        internal_deposit_endpoint: str = "/v5/asset/deposit/query-internal-record",
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._base_url = base_url.rstrip("/")
        self._recv_window = str(recv_window)
        self._timeout = timeout_seconds
        self._internal_deposit_endpoint = internal_deposit_endpoint

    def get_api_key_info(self) -> dict[str, Any]:
        return self._signed_get("/v5/user/query-api")

    def get_internal_deposit_records(
        self,
        *,
        coin: str,
        start_time_ms: int,
        end_time_ms: int,
        cursor: str | None = None,
        limit: int = 50,
    ) -> BybitInternalDepositResult:
        params: dict[str, str] = {
            "coin": coin,
            "startTime": str(start_time_ms),
            "endTime": str(end_time_ms),
            "limit": str(limit),
        }
        if cursor:
            params["cursor"] = cursor

        payload = self._signed_get(self._internal_deposit_endpoint, params=params)
        rows = payload.get("rows") or payload.get("list") or []
        next_cursor = payload.get("nextPageCursor") or payload.get("nextCursor") or payload.get("cursor")
        if not isinstance(rows, list):
            raise BybitClientError("Bybit internal deposit response has invalid rows format")

        records: list[BybitInternalDepositRecord] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            records.append(_parse_internal_deposit_record(item))
        return BybitInternalDepositResult(records=records, next_cursor=str(next_cursor) if next_cursor else None)

    def _signed_get(self, path: str, *, params: dict[str, str] | None = None) -> dict[str, Any]:
        query_params = params or {}
        query_string = parse.urlencode(sorted(query_params.items()))
        timestamp = str(int(datetime.now(timezone.utc).timestamp() * 1000))
        payload = f"{timestamp}{self._api_key}{self._recv_window}{query_string}"
        sign = hmac.new(self._api_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

        url = f"{self._base_url}{path}"
        if query_string:
            url = f"{url}?{query_string}"

        req = request.Request(
            url,
            method="GET",
            headers={
                "X-BAPI-API-KEY": self._api_key,
                "X-BAPI-TIMESTAMP": timestamp,
                "X-BAPI-RECV-WINDOW": self._recv_window,
                "X-BAPI-SIGN": sign,
                "Accept": "application/json",
                "User-Agent": "webster-shop-bybit-client/1.0",
            },
        )
        try:
            with request.urlopen(req, timeout=self._timeout) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else ""
            raise BybitClientError(f"Bybit returned HTTP {exc.code}: {details}") from exc
        except (error.URLError, TimeoutError) as exc:
            raise BybitClientError("Bybit API is temporarily unavailable") from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise BybitClientError("Bybit returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise BybitClientError("Bybit response has invalid format")
        if data.get("retCode") not in (0, "0"):
            raise BybitClientError(str(data.get("retMsg") or "Bybit API error"))
        result = data.get("result")
        if not isinstance(result, dict):
            raise BybitClientError("Bybit response has invalid result payload")
        return result


def _parse_internal_deposit_record(raw: dict[str, Any]) -> BybitInternalDepositRecord:
    amount = Decimal(str(raw.get("amount") or "0"))
    created_raw = raw.get("createdTime") or raw.get("createTime") or 0
    created_ms = int(str(created_raw)) if str(created_raw).isdigit() else 0
    return BybitInternalDepositRecord(
        tx_id=str(raw.get("txID") or raw.get("txId") or raw.get("transferId") or "") or None,
        amount=amount,
        coin=str(raw.get("coin") or "").upper(),
        status=str(raw.get("status") or raw.get("transferStatus") or ""),
        from_member_id=str(raw.get("fromMemberId") or raw.get("fromUid") or "") or None,
        created_time_ms=created_ms,
        raw=raw,
    )
