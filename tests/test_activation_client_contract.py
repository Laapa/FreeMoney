from __future__ import annotations

import json
from typing import Any

from app.activation.client import ActivationAPIClient


class DummyResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None


def test_check_cdk_uses_get_with_query(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        return DummyResponse({"code": 0})

    monkeypatch.setattr("app.activation.client.request.urlopen", fake_urlopen)

    client = ActivationAPIClient(base_url="https://activation.example")
    client.check_cdk("AB C")

    assert captured["method"] == "GET"
    assert captured["url"] == "https://activation.example/check_cdk?cdk=AB+C"


def test_check_token_uses_post_token_payload(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return DummyResponse({"code": 0})

    monkeypatch.setattr("app.activation.client.request.urlopen", fake_urlopen)

    client = ActivationAPIClient(base_url="https://activation.example")
    client.check_token("token-value")

    assert captured["method"] == "POST"
    assert captured["url"] == "https://activation.example/check_token"
    assert captured["body"] == {"token": "token-value"}


def test_create_task_uses_original_payload_shape(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return DummyResponse({"code": 0, "data": {"task_id": "t-1"}})

    monkeypatch.setattr("app.activation.client.request.urlopen", fake_urlopen)

    client = ActivationAPIClient(base_url="https://activation.example")
    client.create_task(cdk="CDK-1", token='{"account":"x"}')

    assert captured["method"] == "POST"
    assert captured["url"] == "https://activation.example/create_task"
    assert captured["body"] == {"cdk": "CDK-1", "token": '{"account":"x"}'}


def test_check_task_uses_get_with_path_task_id(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        return DummyResponse({"code": 0, "data": {"status": "pending"}})

    monkeypatch.setattr("app.activation.client.request.urlopen", fake_urlopen)

    client = ActivationAPIClient(base_url="https://activation.example")
    client.check_task("task/1")

    assert captured["method"] == "GET"
    assert captured["url"] == "https://activation.example/check_task/task%2F1"
