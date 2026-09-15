from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any, Literal, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field


app = FastAPI(title="AgentRun Qwen Agent", version="1.0.0")

DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3.8-flash"
DEFAULT_SYSTEM_PROMPT = "你是一个可靠、简洁、友好的中文 AI 助手。"


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: Any


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = None
    messages: list[ChatMessage] = Field(min_length=1)
    stream: bool = False
    temperature: Optional[float] = Field(default=None, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=None, ge=1)


def _provider_messages(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    if not any(message.role == "user" for message in messages):
        raise HTTPException(status_code=400, detail="messages must contain a user message")
    result = [message.model_dump() for message in messages]
    system_prompt = os.getenv("AGENT_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT).strip()
    if system_prompt and not any(message.role == "system" for message in messages):
        result.insert(0, {"role": "system", "content": system_prompt})
    return result


def _provider_error(response: httpx.Response) -> HTTPException:
    detail = "百炼模型调用失败"
    try:
        body = response.json()
        provider_message = body.get("error", {}).get("message")
        if isinstance(provider_message, str) and provider_message:
            detail = provider_message
    except (ValueError, AttributeError):
        pass
    return HTTPException(status_code=502, detail=detail)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/")
@app.post("/invocations")
@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="DASHSCOPE_API_KEY is not configured")

    model = os.getenv("QWEN_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    base_url = os.getenv("DASHSCOPE_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    payload: dict[str, Any] = {
        "model": model,
        "messages": _provider_messages(request.messages),
        "stream": request.stream,
    }
    if request.temperature is not None:
        payload["temperature"] = request.temperature
    if request.max_tokens is not None:
        payload["max_tokens"] = request.max_tokens

    client = httpx.AsyncClient(timeout=httpx.Timeout(120, connect=10))
    try:
        provider_request = client.build_request(
            "POST",
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        response = await client.send(provider_request, stream=request.stream)
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(status_code=502, detail="无法连接百炼模型服务") from exc

    if response.status_code >= 400:
        await response.aread()
        error = _provider_error(response)
        await response.aclose()
        await client.aclose()
        raise error

    if request.stream:
        async def events() -> AsyncIterator[bytes]:
            try:
                async for chunk in response.aiter_bytes():
                    yield chunk
            finally:
                await response.aclose()
                await client.aclose()

        return StreamingResponse(events(), media_type="text/event-stream")

    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="百炼返回了无效 JSON") from exc
    finally:
        await response.aclose()
        await client.aclose()
