"""Ingestion CLI: markdown corpus → chunks → embeddings → Qdrant.

    python -m ingest.ingest                 # everything: portfolio corpus + every tenant
    python -m ingest.ingest --default       # only the portfolio corpus (ansh_corpus)
    python -m ingest.ingest --tenant cahanlaw [--tenant other]   # only those tenants
    python -m ingest.ingest --tenant cahanlaw --dry-run          # chunk + count, no embedding

Idempotent: each collection is recreated on every run (corpora are tiny, so a
full rebuild is simpler and safer than incremental sync). One collection per
tenant (`demo_<slug>`), so ingesting a demo never touches the portfolio's
`ansh_corpus` or any other tenant.
"""

import argparse
import sys
import uuid
from pathlib import Path

import frontmatter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.chunking import Chunk, chunk_document  # noqa: E402
from app.config import settings  # noqa: E402
from app.tenants import DEFAULT_TENANT, Tenant, all_tenants  # noqa: E402


def get_client():
    from qdrant_client import QdrantClient

    if settings.qdrant_url:
        return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    return QdrantClient(path=settings.qdrant_local_path)


def load_chunks(corpus_dir: Path) -> list[Chunk]:
    files = sorted(corpus_dir.glob("*.md"))
    if not files:
        raise SystemExit(f"No corpus files found in {corpus_dir}")
    chunks: list[Chunk] = []
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
    try:
        shown = corpus_dir.relative_to(Path(__file__).resolve().parents[1])
    except ValueError:
        shown = corpus_dir
    print(f"  {shown}: {len(files)} files → {len(chunks)} chunks")
    return chunks


def ingest(tenant: Tenant, client=None, embedder=None) -> int:
    from qdrant_client.models import Distance, PointStruct, VectorParams

    chunks = load_chunks(tenant.corpus_dir)
    vectors = list(embedder.embed([c.text for c in chunks]))
    dim = len(vectors[0])

    if client.collection_exists(tenant.collection):
        client.delete_collection(tenant.collection)
    client.create_collection(
        collection_name=tenant.collection,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )
    points = [
        PointStruct(
            # Deterministic IDs: re-running ingest maps the same section to the
            # same point instead of accumulating duplicates.
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{c.url}#{c.section}#{i}")),
            vector=vec.tolist(),
            payload={"text": c.text, "title": c.title, "section": c.section, "type": c.doc_type, "url": c.url},
        )
        for i, (c, vec) in enumerate(zip(chunks, vectors))
    ]
    client.upsert(collection_name=tenant.collection, points=points)
    target = settings.qdrant_url or settings.qdrant_local_path
    print(f"  ✓ {len(points)} points → '{tenant.collection}' @ {target}")
    return len(points)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tenant", action="append", default=[], help="tenant slug (repeatable)")
    ap.add_argument("--default", action="store_true", help="only the portfolio corpus")
    ap.add_argument("--dry-run", action="store_true", help="chunk and count only; no embeddings, no Qdrant")
    args = ap.parse_args(argv)

    tenants = all_tenants()
    if args.tenant:
        missing = [s for s in args.tenant if s not in tenants or s == DEFAULT_TENANT.slug]
        if missing:
            raise SystemExit(f"Unknown tenant(s): {missing}. Known: {sorted(tenants)}")
        targets = [tenants[s] for s in args.tenant]
    elif args.default:
        targets = [DEFAULT_TENANT]
    else:
        targets = list(tenants.values())  # portfolio + every tenant

    print(f"Ingesting {len(targets)} corpus/corpora: {[t.slug for t in targets]}")
    if args.dry_run:
        for t in targets:
            load_chunks(t.corpus_dir)
        print("dry run — nothing embedded.")
        return

    from fastembed import TextEmbedding

    print(f"Embedding with {settings.embed_model} ...")
    embedder = TextEmbedding(settings.embed_model, cache_dir=settings.embed_cache_dir)
    client = get_client()
    for t in targets:
        ingest(t, client=client, embedder=embedder)


if __name__ == "__main__":
    main()
