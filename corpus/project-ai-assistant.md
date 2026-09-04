---
title: Project — This AI Assistant (RAG chatbot)
type: project
url: https://github.com/ANSH1370/ansh-ai-assistant
updated: 2026-09-04
---

## What this assistant is

The chat widget you are talking to right now is a production-style retrieval-augmented generation (RAG) assistant that Ansh Mangukiya designed and built himself — it is not a ChatGPT wrapper or a no-code bot builder. It answers questions about Ansh's work by retrieving from a curated knowledge base and citing the sources it used. It is a live example of the kind of AI chatbot Ansh builds for businesses: an assistant trained on a company's own documents that gives grounded, source-cited answers instead of hallucinating.

## How this chatbot was built (architecture)

The request flow is: the portfolio's chat widget sends the conversation to a Next.js API route, which proxies it to a FastAPI backend. The backend runs a LangGraph pipeline with four steps: guard (is the question on-topic? off-topic questions get a polite refusal), rewrite (turn a follow-up question into a standalone search query using the conversation history), retrieve (embed the query and search a Qdrant vector database), and generate (an LLM writes the answer from the retrieved passages and marks which sources it used). Citations are extracted from those markers, so the "Sources" shown under each answer are the passages the model actually relied on.

## Technology stack of this assistant

Python, FastAPI, LangGraph for orchestration, Qdrant Cloud as the vector database, BAAI bge-small-en-v1.5 embeddings via fastembed (ONNX, no GPU needed), and Llama models served through Groq's OpenAI-compatible API. A two-tier model setup keeps costs low: a small fast model handles the guard and rewrite steps, a larger model writes the final answer. The backend is deployed on Render, the portfolio on Vercel. The provider can be swapped by changing one URL — the same design works with OpenAI, Anthropic, or a self-hosted model.

## Knowledge base and ingestion

The knowledge base is a set of Markdown documents about Ansh's experience, projects, skills and FAQs. An ingestion script splits each document into header-aware chunks, prefixes every chunk with its document title and section heading (so retrieval sees context, not a bare paragraph), embeds the chunks and upserts them into Qdrant with metadata (title, section, URL). Updating the assistant's knowledge is: edit a Markdown file, re-run ingestion.

## Evaluation and reliability

The assistant ships with automated evals: unit tests for the chunker and a golden-question retrieval test that checks hit-rate@4 against expected sources, with a quality gate of at least 85% that must pass after any corpus or chunking change. Production safeguards include an on-topic guard, a rate limiter (20 requests per minute per IP), CORS locked to the portfolio domains, capped message sizes and history length, graceful fallbacks so the widget never breaks, and a startup warm-up so the first answer after a cold start is fast.

## What this means for a business

Ansh builds the same kind of system for companies: an AI assistant trained on your website, product docs, FAQs or internal knowledge base, embedded on your site (or in Slack/WhatsApp), answering customers or staff with source-cited answers and handing off to a human when needed. Typical building blocks are the ones in this assistant — document ingestion, vector search, an LLM pipeline with guardrails, evals, and a FastAPI backend — deployed on the client's own infrastructure and API keys so there are no ongoing fees to Ansh. To discuss a project, use the contact form on the portfolio or email anshmangukiya.ai@gmail.com.
