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


def test_check_cdk_uses_get_with_code_query_param(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        return DummyResponse({"code": 0, "data": {"code_hash": "hash-1"}})

    monkeypatch.setattr("app.activation.client.request.urlopen", fake_urlopen)

    client = ActivationAPIClient(base_url="https://activation.example")
    client.check_cdk("AB C")

    assert captured["method"] == "GET"
    assert captured["url"] == "https://activation.example/check_cdk?code=AB+C"


def test_check_token_sends_token_object_dict(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return DummyResponse({"code": 0})

    monkeypatch.setattr("app.activation.client.request.urlopen", fake_urlopen)

    client = ActivationAPIClient(base_url="https://activation.example")
    client.check_token({"uid": "42", "session": "abc"})

    assert captured["method"] == "POST"
    assert captured["url"] == "https://activation.example/check_token"
    assert captured["body"] == {"token": {"uid": "42", "session": "abc"}}


def test_create_task_sends_code_hash_and_user_token(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return DummyResponse({"code": 0, "data": {"task_id": "t-1"}})

    monkeypatch.setattr("app.activation.client.request.urlopen", fake_urlopen)

    client = ActivationAPIClient(base_url="https://activation.example")
    client.create_task(code_hash="hash-1", user_token={"uid": "42"})

    assert captured["method"] == "POST"
    assert captured["url"] == "https://activation.example/create_task"
    assert captured["body"] == {"code_hash": "hash-1", "user_token": {"uid": "42"}}


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
