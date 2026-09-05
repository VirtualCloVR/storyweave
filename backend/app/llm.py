import json
from collections.abc import AsyncIterator
import httpx
from fastapi import HTTPException
from .config import settings

def _endpoint() -> str:
    if not settings.openai_base_url or not settings.openai_model:
        raise HTTPException(status_code=503, detail="OPENAI_BASE_URL and OPENAI_MODEL must be configured")
    return f"{settings.openai_base_url.rstrip('/')}/chat/completions"

def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.openai_api_key:
        headers["Authorization"] = f"Bearer {settings.openai_api_key}"
    return headers

async def stream_completion(messages: list[dict[str, str]]) -> AsyncIterator[str]:
    payload = {"model": settings.openai_model, "messages": messages, "stream": True}
    async with httpx.AsyncClient(timeout=httpx.Timeout(settings.llm_timeout_seconds, connect=10)) as client:
        async with client.stream("POST", _endpoint(), headers=_headers(), json=payload) as response:
            if response.status_code >= 400:
                body = (await response.aread())[:1000].decode(errors="replace")
                raise RuntimeError(f"LLM returned {response.status_code}: {body}")
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    token = json.loads(data)["choices"][0]["delta"].get("content")
                except (KeyError, IndexError, TypeError, json.JSONDecodeError):
                    continue
                if token:
                    yield token

async def complete(messages: list[dict[str, str]]) -> str:
    payload = {"model": settings.openai_model, "messages": messages, "stream": False}
    async with httpx.AsyncClient(timeout=httpx.Timeout(settings.llm_timeout_seconds, connect=10)) as client:
        response = await client.post(_endpoint(), headers=_headers(), json=payload)
        if response.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"LLM returned {response.status_code}")
        try:
            return response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=502, detail="Invalid response from LLM") from exc
