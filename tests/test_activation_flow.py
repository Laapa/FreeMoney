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

    def check_token(self, token: str) -> ActivationAPIResponse:
        return ActivationAPIResponse(self.token_response)

    def create_task(self, *, cdk: str, token: str) -> ActivationAPIResponse:
        return ActivationAPIResponse(self.create_response)

    def check_task(self, task_id: str) -> ActivationAPIResponse:
        return ActivationAPIResponse(self.task_response)


def test_activation_success_flow() -> None:
    service = ActivationFlowService(
        StubActivationClient(
            cdk_response={"code": 0, "msg": "ok"},
            token_response={"code": 0, "msg": "ok"},
            create_response={"code": 0, "data": {"task_id": "task-1"}},
            task_response={"code": 0, "data": {"status": "completed"}},
        )
    )

    result = service.run(cdk="ABC", token_input="token-raw")

    assert result.status == ActivationStatus.SUCCESS
    assert result.task_id == "task-1"
    assert len(result.steps) == 4


def test_activation_fails_for_invalid_cdk() -> None:
    service = ActivationFlowService(
        StubActivationClient(
            cdk_response={"code": 4001, "msg": "Unknown CDK"},
            token_response={"code": 0, "msg": "ok"},
            create_response={"code": 0, "data": {"task_id": "task-1"}},
            task_response={"code": 0, "data": {"status": "completed"}},
        )
    )

    result = service.run(cdk="BAD", token_input="token-raw")

    assert result.status == ActivationStatus.FAILED
    assert result.failure_reason == "Unknown CDK"


def test_activation_fails_for_invalid_token() -> None:
    service = ActivationFlowService(
        StubActivationClient(
            cdk_response={"code": 0, "msg": "ok"},
            token_response={"code": 1002, "msg": "Invalid token"},
            create_response={"code": 0, "data": {"task_id": "task-1"}},
            task_response={"code": 0, "data": {"status": "completed"}},
        )
    )

    result = service.run(cdk="ABC", token_input="bad-token")

    assert result.status == ActivationStatus.FAILED
    assert result.failure_reason == "Invalid token"


def test_activation_fails_when_task_creation_fails() -> None:
    service = ActivationFlowService(
        StubActivationClient(
            cdk_response={"code": 0, "msg": "ok"},
            token_response={"code": 0, "msg": "ok"},
            create_response={"code": 5003, "msg": "quota exceeded"},
            task_response={"code": 0, "data": {"status": "completed"}},
        )
    )

    result = service.run(cdk="ABC", token_input="ok-token")

    assert result.status == ActivationStatus.FAILED
    assert result.failure_reason == "quota exceeded"


def test_activation_pending_result() -> None:
    service = ActivationFlowService(
        StubActivationClient(
            cdk_response={"code": 0, "msg": "ok"},
            token_response={"code": 0, "msg": "ok"},
            create_response={"code": 0, "data": {"task_id": "task-2"}},
            task_response={"code": 0, "data": {"status": "pending"}},
        )
    )

    result = service.run(cdk="ABC", token_input="ok-token")

    assert result.status == ActivationStatus.PENDING
    assert result.task_id == "task-2"


def test_activation_failed_result_from_task_check() -> None:
    service = ActivationFlowService(
        StubActivationClient(
            cdk_response={"code": 0, "msg": "ok"},
            token_response={"code": 0, "msg": "ok"},
            create_response={"code": 0, "data": {"task_id": "task-3"}},
            task_response={"code": 0, "data": {"status": "failed"}, "msg": "account banned"},
        )
    )

    result = service.run(cdk="ABC", token_input="ok-token")

    assert result.status == ActivationStatus.FAILED
    assert result.failure_reason == "account banned"
    assert result.task_id == "task-3"
