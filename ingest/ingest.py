"""Ingestion CLI: corpus/*.md → chunks → embeddings → Qdrant.

Run after any corpus edit:  python -m ingest.ingest
Idempotent: the collection is recreated each run (corpus is tiny, so a full
rebuild is simpler and safer than incremental sync).
"""

import sys
import uuid
from pathlib import Path

import frontmatter
from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.chunking import chunk_document  # noqa: E402
from app.config import settings  # noqa: E402

CORPUS_DIR = Path(__file__).resolve().parents[1] / "corpus"


def get_client() -> QdrantClient:
    if settings.qdrant_url:
        return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    return QdrantClient(path=settings.qdrant_local_path)


def main() -> None:
    files = sorted(CORPUS_DIR.glob("*.md"))
    if not files:
        raise SystemExit(f"No corpus files found in {CORPUS_DIR}")

    chunks = []
    for f in files:
        doc = frontmatter.load(f)
        chunks.extend(
            chunk_document(
                body=doc.content,
                title=str(doc.get("title", f.stem)),
                doc_type=str(doc.get("type", "other")),
                url=str(doc.get("url", "")),
            )
        )
    print(f"Loaded {len(files)} files → {len(chunks)} chunks")

    print(f"Embedding with {settings.embed_model} ...")
    embedder = TextEmbedding(settings.embed_model)
    vectors = list(embedder.embed([c.text for c in chunks]))
    dim = len(vectors[0])

    client = get_client()
    if client.collection_exists(settings.collection):
        client.delete_collection(settings.collection)
    client.create_collection(
        collection_name=settings.collection,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )

    points = [
        PointStruct(
            # Deterministic IDs: re-running ingest maps the same section to the
            # same point instead of accumulating duplicates.
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{c.url}#{c.section}#{i}")),
            vector=vec.tolist(),
            payload={
                "text": c.text,
                "title": c.title,
                "section": c.section,
                "type": c.doc_type,
                "url": c.url,
            },
        )
        for i, (c, vec) in enumerate(zip(chunks, vectors))
    ]
    client.upsert(collection_name=settings.collection, points=points)
    target = settings.qdrant_url or settings.qdrant_local_path
    print(f"Upserted {len(points)} points → '{settings.collection}' @ {target}")


if __name__ == "__main__":
    main()
