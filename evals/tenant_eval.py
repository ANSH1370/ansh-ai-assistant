"""Retrieval quality gate for one tenant — run before sending a demo link.

    python -m evals.tenant_eval --tenant cahanlaw

Reads tenants/<slug>/golden.jsonl — one {"q": ..., "expect_url_contains": ...}
per line (8-10 questions a real visitor would ask, taken from the firm's FAQ /
practice pages) — ingests the tenant corpus into a throwaway local store and
reports hit-rate@4. Below 85% → fix the corpus (junk pages, missing pages),
not the prompt.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

K, MIN_HIT_RATE = 4, 0.85


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", required=True)
    args = ap.parse_args(argv)

    from fastembed import TextEmbedding
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams

    from app.config import settings
    from app.tenants import get_tenant
    from ingest.ingest import load_chunks

    t = get_tenant(args.tenant)
    if t is None or t.is_default:
        sys.exit(f"unknown tenant {args.tenant!r}")
    golden_path = ROOT / "tenants" / t.slug / "golden.jsonl"
    if not golden_path.exists():
        sys.exit(f"write {golden_path} first (see docstring)")
    golden = [json.loads(l) for l in golden_path.read_text(encoding="utf-8").splitlines() if l.strip()]

    chunks = load_chunks(t.corpus_dir)
    embedder = TextEmbedding(settings.embed_model, cache_dir=settings.embed_cache_dir)
    vectors = list(embedder.embed([c.text for c in chunks]))
    client = QdrantClient(":memory:")
    client.create_collection("eval", vectors_config=VectorParams(size=len(vectors[0]), distance=Distance.COSINE))
    client.upsert("eval", points=[
        PointStruct(id=i, vector=v.tolist(), payload={"url": c.url, "title": c.title, "section": c.section})
        for i, (c, v) in enumerate(zip(chunks, vectors))
    ])

    hits, misses = 0, []
    for item in golden:
        qv = list(embedder.query_embed(item["q"]))[0]
        res = client.query_points("eval", query=qv.tolist(), limit=K, with_payload=True)
        urls = [p.payload["url"] for p in res.points]
        if any(item["expect_url_contains"] in u for u in urls):
            hits += 1
        else:
            misses.append((item["q"], [f'{p.payload["title"]} :: {p.payload["section"]}' for p in res.points]))
    rate = hits / len(golden)
    print(f"\n{t.slug}: retrieval hit-rate@{K} = {rate:.0%} ({hits}/{len(golden)})")
    for q, got in misses:
        print(f"  MISS: {q!r}\n        top hits: {got}")
    print("PASS" if rate >= MIN_HIT_RATE else f"FAIL (gate {MIN_HIT_RATE:.0%}) — fix the corpus, not the prompt")
    sys.exit(0 if rate >= MIN_HIT_RATE else 1)


if __name__ == "__main__":
    main()
