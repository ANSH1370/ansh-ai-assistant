"""FastAPI surface: POST /chat + GET /health.

CORS is locked to the portfolio's domains, and a small in-memory rate limiter
protects the free-tier LLM quota. (In-memory is fine on a single Render
instance; swap for Redis if this ever scales past one.)
"""

import time
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import settings
from app.graph import pipeline

app = FastAPI(title="ansh-ai-assistant", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)

_requests: dict[str, deque] = defaultdict(deque)


def _rate_limited(ip: str) -> bool:
    now = time.time()
    window = _requests[ip]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= settings.rate_limit_per_min:
        return True
    window.append(now)
    return False


class Message(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=1000)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=12)


class ChatResponse(BaseModel):
    answer: str
    citations: list[dict]


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest, request: Request) -> ChatResponse:
    ip = request.headers.get("x-forwarded-for", request.client.host or "?").split(",")[0]
    if _rate_limited(ip):
        raise HTTPException(429, "Too many requests — try again in a minute.")

    last_user = next((m for m in reversed(req.messages) if m.role == "user"), None)
    if last_user is None:
        raise HTTPException(400, "No user message found.")
    history = [m.model_dump() for m in req.messages[:-1]]

    state = pipeline.invoke({"question": last_user.content, "history": history})
    return ChatResponse(answer=state["answer"], citations=state.get("citations", []))
