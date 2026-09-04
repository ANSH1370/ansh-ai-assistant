# ansh-ai-assistant

A retrieval-augmented generation (RAG) assistant that answers questions about
Ansh Mangukiya's work — with citations. Built with open-source components and
served as the chat widget on [anshmangukiya.vercel.app](https://anshmangukiya.vercel.app).

```
Portfolio widget ──POST /chat──▶ FastAPI on Render
                                    │
                        LangGraph pipeline:
                 guard → rewrite → retrieve → generate
                   │                  │            │
              off-topic?         Qdrant (bge     Groq
              polite refusal     embeddings)   (Llama 3.x)
```

## Stack & why

| Piece | Choice | Why |
|---|---|---|
| Embeddings | `bge-small-en-v1.5` via **fastembed** | ONNX runtime, no torch → fits a 512MB Render instance; same model quality |
| Vector DB | **Qdrant** (Cloud free tier; local on-disk in dev) | Real vector DB, metadata payloads, survives restarts |
| Orchestration | **LangGraph** | Explicit, testable pipeline: each node is a plain function |
| LLM | Llama via **Groq** OpenAI-compatible API | Free tier, very fast tokens, zero ops; provider swap = one URL |
| Two-tier models | 8B for guard/rewrite, 70B for answers | Cheap steps stay cheap; quality where it matters |

## Setup

Requires Python 3.11–3.13.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then fill in GROQ_API_KEY (+ Qdrant creds for cloud)
```

## Develop locally (no cloud needed)

Leave `QDRANT_URL` empty in `.env` — Qdrant runs as a local on-disk store.

```bash
python -m ingest.ingest            # corpus/*.md → chunks → embeddings → vector store
uvicorn app.main:app --reload      # API on http://localhost:8000
```

Smoke test:

```bash
curl -s localhost:8000/chat -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"What does Ansh do at Commercient?"}]}'
```

## Evals

```bash
pytest evals/ -s
```

- `test_chunking.py` — chunker unit tests (fast, offline)
- `test_retrieval.py` — golden-set retrieval hit-rate@4 (offline; gate: ≥85%)

Re-run after any corpus or chunking change. If retrieval drops, fix the corpus
or chunking — don't paper over it in the prompt.

## Deploy (Render)

1. Push this repo to GitHub → Render → New → Web Service → connect repo
2. Build command: `pip install -r requirements.txt && python -m ingest.ingest`
3. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Env vars: `GROQ_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`, `ALLOWED_ORIGINS`
5. Run ingestion against Qdrant Cloud once locally (set `QDRANT_URL` in `.env`,
   run `python -m ingest.ingest`) — or let the build command do it on each deploy.

### Cold starts (free tier)

Render's free instance sleeps after 15 min idle and takes ~30-50 s to wake.
Three layers keep the first answer fast and real:

- **Startup warm-up** — the FastAPI lifespan hook loads the embedding model and
  opens the Qdrant connection *before* the port opens, so the first `/chat`
  costs the same as any other.
- **Model cache in the project dir** — `EMBED_CACHE_DIR` defaults to
  `.fastembed_cache/`, so the model downloaded by `ingest` at build time is
  still there at runtime (the default `/tmp` cache is not).
- **Keep-alive ping** — `.github/workflows/keepalive.yml` hits the portfolio's
  warmup route every 10 min (free on a public repo). Any external pinger
  (cron-job.org, UptimeRobot) works the same way.

The portfolio side warms the backend on page load and waits up to 50 s for
the RAG answer before falling back to its FAQ mode.

## Updating the knowledge base

Edit `corpus/*.md` → run `python -m ingest.ingest` → done. Frontmatter `url`
is what citations link to; keep it accurate.

## API

`POST /chat` → `{"messages": [{"role": "user|assistant", "content": "..."}]}`
returns `{"answer": str, "citations": [{"title": str, "url": str}]}`.
Rate limit: 20 req/min/IP. CORS: portfolio domains only.
