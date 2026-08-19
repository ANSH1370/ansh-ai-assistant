"""The LangGraph pipeline: guard → rewrite → retrieve → generate.

Kept deliberately linear with one conditional edge — every node is independently
testable, and the graph mirrors how you'd explain the system on a whiteboard.
"""

import json
import re
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app import prompts
from app.config import settings
from app.llm import chat
from app.retrieval import Hit, search


class ChatState(TypedDict, total=False):
    history: list[dict]      # [{role, content}] — prior turns, user/assistant only
    question: str            # latest user message
    on_topic: bool
    standalone: str          # rewritten search query
    hits: list[Hit]
    answer: str
    citations: list[dict]    # [{title, url}]


# ── nodes ────────────────────────────────────────────────────────────────

def guard(state: ChatState) -> ChatState:
    try:
        raw = chat(
            [
                {"role": "system", "content": prompts.GUARD_PROMPT},
                {"role": "user", "content": state["question"][:1000]},
            ],
            model=settings.fast_model,
            json_mode=True,
            max_tokens=20,
            temperature=0.0,
        )
        on_topic = bool(json.loads(raw).get("on_topic", False))
    except Exception:
        on_topic = True  # fail open: a broken guard shouldn't kill the demo
    return {"on_topic": on_topic}


def refuse(state: ChatState) -> ChatState:
    return {"answer": prompts.REFUSAL_MESSAGE, "citations": []}


def rewrite(state: ChatState) -> ChatState:
    # No history → the question is already standalone; skip one LLM call.
    if not state.get("history"):
        return {"standalone": state["question"]}
    convo = "\n".join(f'{m["role"]}: {m["content"]}' for m in state["history"][-6:])
    try:
        standalone = chat(
            [
                {"role": "system", "content": prompts.REWRITE_PROMPT},
                {"role": "user", "content": f"Conversation:\n{convo}\n\nLatest message: {state['question']}"},
            ],
            model=settings.fast_model,
            max_tokens=60,
            temperature=0.0,
        ).strip()
    except Exception:
        standalone = state["question"]
    return {"standalone": standalone or state["question"]}


def retrieve(state: ChatState) -> ChatState:
    return {"hits": search(state["standalone"])}


def generate(state: ChatState) -> ChatState:
    hits = state["hits"]
    context = "\n\n".join(
        f"[{i + 1}] {h.title} ({h.url})\n{h.text}" for i, h in enumerate(hits)
    )
    answer = chat(
        [
            {"role": "system", "content": prompts.ANSWER_PROMPT.format(context=context)},
            *state.get("history", [])[-4:],
            {"role": "user", "content": state["question"]},
        ],
        model=settings.gen_model,
        max_tokens=500,
    )

    # Citations = the context blocks the model actually referenced.
    cited_idx = {int(n) - 1 for n in re.findall(r"\[(\d+)\]", answer)}
    cited = [hits[i] for i in sorted(cited_idx) if 0 <= i < len(hits)]
    if not cited and hits:
        cited = hits[:2]  # model answered without markers — surface top sources

    seen, citations = set(), []
    for h in cited:
        if h.url not in seen:
            seen.add(h.url)
            citations.append({"title": h.title, "url": h.url})
    return {"answer": answer, "citations": citations}


# ── graph wiring ─────────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(ChatState)
    g.add_node("guard", guard)
    g.add_node("refuse", refuse)
    g.add_node("rewrite", rewrite)
    g.add_node("retrieve", retrieve)
    g.add_node("generate", generate)

    g.set_entry_point("guard")
    g.add_conditional_edges(
        "guard",
        lambda s: "rewrite" if s["on_topic"] else "refuse",
        {"rewrite": "rewrite", "refuse": "refuse"},
    )
    g.add_edge("rewrite", "retrieve")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", END)
    g.add_edge("refuse", END)
    return g.compile()


pipeline = build_graph()
