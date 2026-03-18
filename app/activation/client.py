from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib import error, request
import json


class ActivationClientError(Exception):
    """Raised when activation API request fails."""


@dataclass(slots=True)
class ActivationAPIResponse:
    payload: dict[str, Any]

    @property
    def message(self) -> str | None:
        raw = self.payload.get("message") or self.payload.get("detail")
        return str(raw) if raw is not None else None


class ActivationAPIClient:
    def __init__(self, *, base_url: str, timeout_seconds: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def check_cdk(self, cdk: str) -> ActivationAPIResponse:
        return self._post("/check_cdk", {"cdk": cdk})

    def check_token(self, token_payload: dict[str, Any]) -> ActivationAPIResponse:
        return self._post("/check_token", token_payload)

    def create_task(self, *, cdk: str, token_payload: dict[str, Any]) -> ActivationAPIResponse:
        return self._post("/create_task", {"cdk": cdk, **token_payload})

    def check_task(self, task_id: str) -> ActivationAPIResponse:
        return self._post("/check_task", {"task_id": task_id})

    def _post(self, path: str, payload: dict[str, Any]) -> ActivationAPIResponse:
        url = f"{self._base_url}{path}"
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")

        try:
            with request.urlopen(req, timeout=self._timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else ""
            raise ActivationClientError(f"Activation API returned HTTP {exc.code}: {details}") from exc
        except (error.URLError, TimeoutError):
            raise ActivationClientError("Activation service is temporarily unavailable. Please retry shortly.")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ActivationClientError("Activation API response format is invalid.") from exc

        if not isinstance(data, dict):
            raise ActivationClientError("Activation API response format is invalid.")

        return ActivationAPIResponse(payload=data)
