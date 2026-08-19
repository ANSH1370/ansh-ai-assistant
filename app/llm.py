"""Thin Groq client over its OpenAI-compatible endpoint.

Plain httpx instead of an SDK: one fewer dependency, and the request shape
stays visible. Swapping providers (Together/Cerebras) = change BASE_URL.
"""

import httpx

from app.config import settings

BASE_URL = "https://api.groq.com/openai/v1/chat/completions"


def chat(
    messages: list[dict],
    model: str | None = None,
    json_mode: bool = False,
    max_tokens: int = 700,
    temperature: float = 0.3,
) -> str:
    payload: dict = {
        "model": model or settings.gen_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    with httpx.Client(timeout=30) as client:
        for attempt in (1, 2):
            resp = client.post(
                BASE_URL,
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                json=payload,
            )
            if resp.status_code in (429, 500, 502, 503) and attempt == 1:
                continue  # one retry on transient failures
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
    raise RuntimeError("unreachable")
