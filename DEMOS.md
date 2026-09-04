# Demo assistants for prospects (and, later, clients)

One prospect = one **tenant**: a folder `tenants/<slug>/` with the crawled
corpus, a `tenant.json` config, and its own Qdrant collection `demo_<slug>`.
The portfolio assistant is untouched (it stays on `ansh_corpus` with its own
prompts), and tenants never see each other's data. The live page is
`https://anshmangukiya.vercel.app/demo/<slug>`.

## Build one (≈30 min once you've done it once)

```bash
cd ~/Projects/ansh-ai-assistant && source myenv/bin/activate
pip install -r requirements.txt            # first time only (adds trafilatura)

# 1. Crawl their public site → tenants/<slug>/corpus/*.md  (+ draft tenant.json)
python -m ingest.crawl --slug cahanlaw --url https://www.cahanlaw.com
#    Useful flags: --max-pages 40   --exclude "/blog/"   --include "/(probate|estate|contact|about)"
#    --urls urls.txt (explicit list)   --delay 1.0   (robots.txt is respected)

# 2. Review: open tenants/cahanlaw/corpus/, delete junk pages (login, thin pages),
#    and EDIT tenants/cahanlaw/tenant.json — description, contact line, starters,
#    welcome, disclaimer, languages (["en","es"] for Spanish-speaking firms → the
#    rewrite step searches in English and the answer follows the visitor's language).

# 3. Golden questions (8-10 a real visitor would ask, from their FAQ/practice pages):
#    tenants/cahanlaw/golden.jsonl → {"q": "How long does probate take?", "expect_url_contains": "/probate"}
python -m evals.tenant_eval --tenant cahanlaw      # gate: hit-rate@4 ≥ 85%

# 4. Ingest into Qdrant Cloud (QDRANT_URL in .env) — only this tenant's collection
python -m ingest.ingest --tenant cahanlaw

# 5. Commit + push. Render redeploys (its build runs `python -m ingest.ingest`, which
#    now ingests the portfolio corpus AND every tenant — idempotent). Then open
#    https://anshmangukiya.vercel.app/demo/cahanlaw and ask it the golden questions.
git add tenants/cahanlaw && git commit -m "demo: cahanlaw" && git push
```

## What the tenant assistant does differently

- **Isolation:** `retrieve` searches `demo_<slug>` only; prompts are templated from
  `tenant.json` (`app/prompts.py` → `TENANT_*`), so it speaks as the firm's assistant
  and never mentions Ansh.
- **Guardrails (law-firm safe):** answers only from the firm's published pages with
  source links; no legal/medical/financial advice; questions about the visitor's own
  situation get the general info + "book a consultation"; never quotes fees that
  aren't on the site; asks for name / contact / matter when the visitor wants to be
  contacted. The page shows the disclaimer before the first message.
- **Lead capture:** the demo page's form posts to the portfolio's Web3Forms relay,
  tagged `Demo lead — <firm>`, so leads reach Ansh's inbox during the demo (the
  firm's inbox once live).
- **Routes:** `GET /demo/<slug>` (public config for the page) and
  `POST /demo/<slug>/chat`. `POST /chat` is the portfolio assistant, unchanged.

## Going live for a paying client

Same tenant, three changes: (1) `lead_email` → their inbox and the page/form point
there, (2) their own Groq/Qdrant keys via env overrides (or a separate Render
service per client if they want full isolation), (3) the widget embed snippet on
their site instead of the demo page. Corpus updates = re-crawl or hand-edit the
markdown, re-ingest.
