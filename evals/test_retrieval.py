"""Retrieval quality gate: hit-rate@k against the golden set.

Runs fully offline (fastembed + local Qdrant) — no API keys needed.
Ingests the corpus into a temp store, then checks that for each golden
question, a chunk from the expected source appears in the top-k results.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

GOLDEN = [
    json.loads(line)
    for line in (ROOT / "evals" / "golden.jsonl").read_text(encoding="utf-8").splitlines()
    if line.strip()
]

K = 4
MIN_HIT_RATE = 0.85


@pytest.fixture(scope="session")
def store(tmp_path_factory):
    """Ingest the real corpus into a throwaway local Qdrant + return a search fn."""
    import frontmatter
    from fastembed import TextEmbedding
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams

    from app.chunking import chunk_document
    from app.config import settings

    chunks = []
    for f in sorted((ROOT / "corpus").glob("*.md")):
        doc = frontmatter.load(f)
        chunks.extend(
            chunk_document(
                body=doc.content,
                title=str(doc.get("title", f.stem)),
                doc_type=str(doc.get("type", "other")),
                url=str(doc.get("url", "")),
            )
        )
    assert chunks, "corpus produced no chunks"

    embedder = TextEmbedding(settings.embed_model, cache_dir=settings.embed_cache_dir)
    vectors = list(embedder.embed([c.text for c in chunks]))

    client = QdrantClient(path=str(tmp_path_factory.mktemp("qdrant")))
    client.create_collection(
        "eval",
        vectors_config=VectorParams(size=len(vectors[0]), distance=Distance.COSINE),
    )
    client.upsert(
        "eval",
        points=[
            PointStruct(id=i, vector=v.tolist(), payload={"url": c.url, "title": c.title})
            for i, (c, v) in enumerate(zip(chunks, vectors))
        ],
    )

    def search(query: str, k: int = K) -> list[str]:
        qv = list(embedder.query_embed(query))[0]
        res = client.query_points("eval", query=qv.tolist(), limit=k, with_payload=True)
        return [p.payload["url"] for p in res.points]

    return search


def test_hit_rate(store):
    hits, misses = 0, []
    for item in GOLDEN:
        urls = store(item["q"])
        if any(item["expect_url_contains"] in u for u in urls):
            hits += 1
        else:
            misses.append((item["q"], urls))

    rate = hits / len(GOLDEN)
    print(f"\nretrieval hit-rate@{K}: {rate:.0%} ({hits}/{len(GOLDEN)})")
    for q, urls in misses:
        print(f"  MISS: {q!r} → {urls}")
    assert rate >= MIN_HIT_RATE, f"hit-rate {rate:.0%} below {MIN_HIT_RATE:.0%}"
