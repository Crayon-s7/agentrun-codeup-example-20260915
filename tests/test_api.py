from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import main


client = TestClient(main.app)


class FakeProviderResponse:
    def __init__(self, request: dict[str, Any], stream: bool) -> None:
        self.request = request
        self.stream = stream
        self.status_code = 200

    def json(self) -> dict[str, Any]:
        return {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "model": self.request["json"]["model"],
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "AGENTRUN_OK"}, "finish_reason": "stop"}],
        }

    async def aread(self) -> bytes:
        return json.dumps(self.json()).encode()

    async def aiter_bytes(self):
        yield b'data: {"choices":[{"delta":{"content":"AGENTRUN_OK"}}]}\n\n'
        yield b"data: [DONE]\n\n"

    async def aclose(self) -> None:
        return None


class FakeProviderClient:
    last_request: dict[str, Any] | None = None

    def __init__(self, *args, **kwargs) -> None:
        pass

    def build_request(self, method: str, url: str, **kwargs) -> dict[str, Any]:
        request = {"method": method, "url": url, **kwargs}
        FakeProviderClient.last_request = request
        return request

    async def send(self, request: dict[str, Any], stream: bool = False):
        return FakeProviderResponse(request, stream)

    async def aclose(self) -> None:
        return None


@pytest.fixture(autouse=True)
def provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-only-key")
    monkeypatch.setenv("QWEN_MODEL", "qwen3.8-flash")
    monkeypatch.setenv("DASHSCOPE_BASE_URL", "https://example.invalid/compatible-mode/v1")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeProviderClient)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("path", ["/", "/invocations", "/v1/chat/completions"])
def test_supported_invocation_routes(path: str) -> None:
    response = client.post(path, json={"messages": [{"role": "user", "content": "ping"}]})
    assert response.status_code == 200
    assert response.json()["model"] == "qwen3.8-flash"


def test_calls_configured_provider_and_injects_system_prompt() -> None:
    client.post("/invocations", json={"messages": [{"role": "user", "content": "ping"}]})
    request = FakeProviderClient.last_request
    assert request is not None
    assert request["url"] == "https://example.invalid/compatible-mode/v1/chat/completions"
    assert request["json"]["messages"][0]["role"] == "system"
    assert request["headers"]["Authorization"] == "Bearer test-only-key"


def test_client_cannot_override_deployment_model() -> None:
    response = client.post(
        "/invocations",
        json={"model": "another-model", "messages": [{"role": "user", "content": "ping"}]},
    )
    assert response.status_code == 200
    assert FakeProviderClient.last_request["json"]["model"] == "qwen3.8-flash"


def test_streaming_completion() -> None:
    response = client.post(
        "/invocations",
        json={"messages": [{"role": "user", "content": "ping"}], "stream": True},
    )
    assert response.status_code == 200
    assert "data: [DONE]" in response.text


def test_requires_user_message() -> None:
    response = client.post(
        "/invocations",
        json={"messages": [{"role": "system", "content": "help"}]},
    )
    assert response.status_code == 400


def test_missing_api_key_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DASHSCOPE_API_KEY")
    response = client.post(
        "/invocations",
        json={"messages": [{"role": "user", "content": "ping"}]},
    )
    assert response.status_code == 503
