from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

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

    def run(self, *, cdk: str, token_input: str) -> ActivationFlowResult:
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

            token_response = self._client.check_token(token_input)
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

            task_response = self._client.create_task(cdk=cdk, token=token_input)
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

    # Original client/API may return top-level booleans.
    for key in ("ok", "success", "valid"):
        value = payload.get(key)
        if isinstance(value, bool):
            return value

    # Some responses use numeric/code semantics.
    code = payload.get("code")
    if isinstance(code, int):
        return code == 0

    status = str(payload.get("status", "")).lower()
    if status in {"ok", "success", "valid"}:
        return True
    if status in {"failed", "error", "invalid"}:
        return False

    return bool(payload.get("data"))


def _extract_task_id(response: ActivationAPIResponse) -> str | None:
    payload = response.payload
    for key in ("task_id", "id", "taskId"):
        value = payload.get(key)
        if value:
            return str(value)

    data = payload.get("data")
    if isinstance(data, dict):
        value = data.get("task_id") or data.get("id")
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

    # check_task may wrap task object in data/task.
    task_payload = payload
    if isinstance(payload.get("data"), dict):
        task_payload = payload["data"]
    elif isinstance(payload.get("task"), dict):
        task_payload = payload["task"]

    raw_status = str(task_payload.get("status", payload.get("status", ""))).lower()
    if raw_status in {"success", "done", "completed", "finish", "finished"}:
        return ActivationStatus.SUCCESS
    if raw_status in {"pending", "processing", "in_progress", "created", "queued", "running"}:
        return ActivationStatus.PENDING
    if raw_status in {"failed", "error", "canceled", "cancelled"}:
        return ActivationStatus.FAILED

    if task_payload.get("ok") is True or task_payload.get("success") is True:
        return ActivationStatus.SUCCESS

    code = task_payload.get("code", payload.get("code"))
    if isinstance(code, int):
        if code == 0:
            return ActivationStatus.SUCCESS
        if code == 102:
            return ActivationStatus.PENDING

    return ActivationStatus.FAILED
