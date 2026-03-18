from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.activation.client import ActivationAPIClient, ActivationAPIResponse, ActivationClientError


class ActivationStage(str, Enum):
    CHECK_CDK = "check_cdk"
    CHECK_TOKEN = "check_token"
    CREATE_TASK = "create_task"
    CHECK_TASK = "check_task"


class ActivationStatus(str, Enum):
    SUCCESS = "success"
    PENDING = "pending"
    FAILED = "failed"


@dataclass(slots=True)
class ActivationStepResult:
    stage: ActivationStage
    ok: bool
    message: str


@dataclass(slots=True)
class ActivationFlowResult:
    status: ActivationStatus
    steps: list[ActivationStepResult]
    message: str
    task_id: str | None = None
    failure_reason: str | None = None


class ActivationFlowService:
    def __init__(self, client: ActivationAPIClient) -> None:
        self._client = client

    def run(self, *, cdk: str, token_payload: dict[str, Any]) -> ActivationFlowResult:
        steps: list[ActivationStepResult] = []

        try:
            cdk_response = self._client.check_cdk(cdk)
            if not _response_ok(cdk_response):
                message = cdk_response.message or "Activation code is invalid or expired."
                steps.append(ActivationStepResult(stage=ActivationStage.CHECK_CDK, ok=False, message=message))
                return ActivationFlowResult(
                    status=ActivationStatus.FAILED,
                    steps=steps,
                    message="Activation code validation failed.",
                    failure_reason=message,
                )
            steps.append(ActivationStepResult(stage=ActivationStage.CHECK_CDK, ok=True, message="Activation code confirmed."))

            token_response = self._client.check_token(token_payload)
            if not _response_ok(token_response):
                message = token_response.message or "Account token data is invalid."
                steps.append(ActivationStepResult(stage=ActivationStage.CHECK_TOKEN, ok=False, message=message))
                return ActivationFlowResult(
                    status=ActivationStatus.FAILED,
                    steps=steps,
                    message="Token validation failed.",
                    failure_reason=message,
                )
            steps.append(ActivationStepResult(stage=ActivationStage.CHECK_TOKEN, ok=True, message="Token payload accepted."))

            task_response = self._client.create_task(cdk=cdk, token_payload=token_payload)
            task_id = _extract_task_id(task_response)
            if not task_id:
                message = task_response.message or "Activation task could not be created."
                steps.append(ActivationStepResult(stage=ActivationStage.CREATE_TASK, ok=False, message=message))
                return ActivationFlowResult(
                    status=ActivationStatus.FAILED,
                    steps=steps,
                    message="Task creation failed.",
                    failure_reason=message,
                )
            steps.append(ActivationStepResult(stage=ActivationStage.CREATE_TASK, ok=True, message="Activation task started."))

            task_check = self._client.check_task(task_id)
            task_status = _extract_task_status(task_check)
            steps.append(
                ActivationStepResult(
                    stage=ActivationStage.CHECK_TASK,
                    ok=task_status != ActivationStatus.FAILED,
                    message=task_check.message or "Task status received.",
                )
            )

            if task_status == ActivationStatus.SUCCESS:
                return ActivationFlowResult(
                    status=ActivationStatus.SUCCESS,
                    steps=steps,
                    message="Activation completed successfully.",
                    task_id=task_id,
                )
            if task_status == ActivationStatus.PENDING:
                return ActivationFlowResult(
                    status=ActivationStatus.PENDING,
                    steps=steps,
                    message="Activation task is still processing.",
                    task_id=task_id,
                )

            reason = task_check.message or "Activation failed at task execution stage."
            return ActivationFlowResult(
                status=ActivationStatus.FAILED,
                steps=steps,
                message="Activation failed.",
                task_id=task_id,
                failure_reason=reason,
            )
        except ActivationClientError:
            steps.append(
                ActivationStepResult(
                    stage=ActivationStage.CHECK_TASK,
                    ok=False,
                    message="Activation service is temporarily unavailable. Please try again.",
                )
            )
            return ActivationFlowResult(
                status=ActivationStatus.FAILED,
                steps=steps,
                message="Activation service error.",
                failure_reason="Activation service is temporarily unavailable. Please try again.",
            )


def _response_ok(response: ActivationAPIResponse) -> bool:
    payload = response.payload
    candidates = ("ok", "success", "valid")
    for key in candidates:
        value = payload.get(key)
        if isinstance(value, bool):
            return value
    status = str(payload.get("status", "")).lower()
    return status in {"ok", "success", "valid"}


def _extract_task_id(response: ActivationAPIResponse) -> str | None:
    payload = response.payload
    for key in ("task_id", "id", "taskId"):
        value = payload.get(key)
        if value:
            return str(value)
    nested = payload.get("task")
    if isinstance(nested, dict):
        value = nested.get("id") or nested.get("task_id")
        if value:
            return str(value)
    return None


def _extract_task_status(response: ActivationAPIResponse) -> ActivationStatus:
    payload = response.payload
    raw_status = str(payload.get("status", "")).lower()
    if raw_status in {"success", "done", "completed"}:
        return ActivationStatus.SUCCESS
    if raw_status in {"pending", "processing", "in_progress", "created"}:
        return ActivationStatus.PENDING
    if raw_status in {"failed", "error"}:
        return ActivationStatus.FAILED

    # Fallbacks for payloads that only expose booleans.
    if payload.get("ok") is True or payload.get("success") is True:
        return ActivationStatus.SUCCESS
    return ActivationStatus.FAILED
