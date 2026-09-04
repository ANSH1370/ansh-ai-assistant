"""Query-time retrieval: embed the query, search Qdrant, return typed hits."""

from dataclasses import dataclass
from functools import lru_cache

from fastembed import TextEmbedding
from qdrant_client import QdrantClient

from app.config import settings


@dataclass
class Hit:
    text: str
    title: str
    section: str
    url: str
    score: float


@lru_cache(maxsize=1)
def _embedder() -> TextEmbedding:
    # Loaded once per process; ~30MB ONNX model, no GPU needed.
    return TextEmbedding(settings.embed_model, cache_dir=settings.embed_cache_dir)


@lru_cache(maxsize=1)
def _client() -> QdrantClient:
    if settings.qdrant_url:
        return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    return QdrantClient(path=settings.qdrant_local_path)


def search(query: str, top_k: int | None = None, collection: str | None = None) -> list[Hit]:
    # query_embed applies BGE's query-side instruction prefix — passages and
    # queries are embedded differently on purpose (that's how BGE was trained).
    vector = list(_embedder().query_embed(query))[0]
    res = _client().query_points(
        collection_name=collection or settings.collection,
        query=vector.tolist(),
        limit=top_k or settings.top_k,
        with_payload=True,
    )
    return [
        Hit(
            text=p.payload.get("text", ""),
            title=p.payload.get("title", ""),
            section=p.payload.get("section", ""),
            url=p.payload.get("url", ""),
            score=p.score,
        )
        for p in res.points
    ]


def warm() -> None:
    """Load the embedder and open the vector store before serving traffic.

    Called from the FastAPI lifespan hook. Without this, the first question
    after a cold start pays model loading + connection setup on top of the
    LLM calls and blows the portfolio's request timeout, so visitors get a
    fallback answer instead of the real RAG one.
    """
    _embedder()
    _client()
    try:
        search("warmup", top_k=1)
    except Exception as exc:  # e.g. collection not ingested yet — don't block boot
        print(f"[retrieval] warmup search skipped: {exc}")
