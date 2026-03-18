from __future__ import annotations

from dataclasses import dataclass

from app.activation.client import ActivationAPIResponse
from app.services.activation import ActivationFlowService, ActivationStatus


@dataclass
class StubActivationClient:
    cdk_response: dict
    token_response: dict
    create_response: dict
    task_response: dict

    def check_cdk(self, cdk: str) -> ActivationAPIResponse:
        return ActivationAPIResponse(self.cdk_response)

    def check_token(self, token_payload: dict) -> ActivationAPIResponse:
        return ActivationAPIResponse(self.token_response)

    def create_task(self, *, cdk: str, token_payload: dict) -> ActivationAPIResponse:
        return ActivationAPIResponse(self.create_response)

    def check_task(self, task_id: str) -> ActivationAPIResponse:
        return ActivationAPIResponse(self.task_response)


def test_activation_success_flow() -> None:
    service = ActivationFlowService(
        StubActivationClient(
            cdk_response={"ok": True},
            token_response={"valid": True},
            create_response={"task_id": "task-1", "ok": True},
            task_response={"status": "success", "message": "done"},
        )
    )

    result = service.run(cdk="ABC", token_payload={"token": "X"})

    assert result.status == ActivationStatus.SUCCESS
    assert result.task_id == "task-1"
    assert len(result.steps) == 4


def test_activation_fails_for_invalid_cdk() -> None:
    service = ActivationFlowService(
        StubActivationClient(
            cdk_response={"ok": False, "message": "Unknown CDK"},
            token_response={"valid": True},
            create_response={"task_id": "task-1"},
            task_response={"status": "success"},
        )
    )

    result = service.run(cdk="BAD", token_payload={"token": "X"})

    assert result.status == ActivationStatus.FAILED
    assert result.failure_reason == "Unknown CDK"


def test_activation_fails_for_invalid_token() -> None:
    service = ActivationFlowService(
        StubActivationClient(
            cdk_response={"ok": True},
            token_response={"valid": False, "message": "Invalid token"},
            create_response={"task_id": "task-1"},
            task_response={"status": "success"},
        )
    )

    result = service.run(cdk="ABC", token_payload={"token": "bad"})

    assert result.status == ActivationStatus.FAILED
    assert result.failure_reason == "Invalid token"


def test_activation_fails_when_task_creation_fails() -> None:
    service = ActivationFlowService(
        StubActivationClient(
            cdk_response={"ok": True},
            token_response={"valid": True},
            create_response={"ok": False, "message": "quota exceeded"},
            task_response={"status": "success"},
        )
    )

    result = service.run(cdk="ABC", token_payload={"token": "ok"})

    assert result.status == ActivationStatus.FAILED
    assert result.failure_reason == "quota exceeded"


def test_activation_pending_result() -> None:
    service = ActivationFlowService(
        StubActivationClient(
            cdk_response={"ok": True},
            token_response={"valid": True},
            create_response={"task_id": "task-2"},
            task_response={"status": "pending", "message": "still running"},
        )
    )

    result = service.run(cdk="ABC", token_payload={"token": "ok"})

    assert result.status == ActivationStatus.PENDING
    assert result.task_id == "task-2"


def test_activation_failed_result_from_task_check() -> None:
    service = ActivationFlowService(
        StubActivationClient(
            cdk_response={"ok": True},
            token_response={"valid": True},
            create_response={"task_id": "task-3"},
            task_response={"status": "failed", "message": "account banned"},
        )
    )

    result = service.run(cdk="ABC", token_payload={"token": "ok"})

    assert result.status == ActivationStatus.FAILED
    assert result.failure_reason == "account banned"
    assert result.task_id == "task-3"
