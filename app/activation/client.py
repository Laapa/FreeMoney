from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request


class ActivationClientError(Exception):
    """Raised when activation API request fails."""


@dataclass(slots=True)
class ActivationAPIResponse:
    payload: dict[str, Any]

    @property
    def message(self) -> str | None:
        raw = (
            self.payload.get("message")
            or self.payload.get("msg")
            or self.payload.get("detail")
            or self.payload.get("error")
        )
        return str(raw) if raw is not None else None


class ActivationAPIClient:
    """HTTP client that mirrors the original activation API contract exactly.

    Contract:
    - check_cdk(code) -> GET /check_cdk?code=...
    - check_token(token_dict) -> POST /check_token with {"token": <dict>}
    - create_task(code_hash, user_token) -> POST /create_task with {"code_hash": ..., "user_token": ...}
    - check_task(task_id) -> GET /check_task/<task_id>
    """

    def __init__(self, *, base_url: str, timeout_seconds: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def check_cdk(self, code: str) -> ActivationAPIResponse:
        query = parse.urlencode({"code": code})
        return self._request("GET", f"/check_cdk?{query}")

    def check_token(self, token_dict: dict[str, Any]) -> ActivationAPIResponse:
        return self._request("POST", "/check_token", {"token": token_dict})

    def create_task(self, *, code_hash: str, user_token: dict[str, Any]) -> ActivationAPIResponse:
        return self._request("POST", "/create_task", {"code_hash": code_hash, "user_token": user_token})

    def check_task(self, task_id: str) -> ActivationAPIResponse:
        safe_task_id = parse.quote(task_id, safe="")
        return self._request("GET", f"/check_task/{safe_task_id}")

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> ActivationAPIResponse:
        url = f"{self._base_url}{path}"
        body: bytes | None = None
        headers: dict[str, str] = {}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = request.Request(url, data=body, headers=headers, method=method)

        try:
            with request.urlopen(req, timeout=self._timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else ""
            raise ActivationClientError(f"Activation API returned HTTP {exc.code}: {details}") from exc
        except (error.URLError, TimeoutError) as exc:
            raise ActivationClientError("Activation service is temporarily unavailable. Please retry shortly.") from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ActivationClientError("Activation API response format is invalid.") from exc

        if not isinstance(data, dict):
            raise ActivationClientError("Activation API response format is invalid.")

        return ActivationAPIResponse(payload=data)
