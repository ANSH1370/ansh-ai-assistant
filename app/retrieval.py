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
    return TextEmbedding(settings.embed_model)


@lru_cache(maxsize=1)
def _client() -> QdrantClient:
    if settings.qdrant_url:
        return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    return QdrantClient(path=settings.qdrant_local_path)


def search(query: str, top_k: int | None = None) -> list[Hit]:
    # query_embed applies BGE's query-side instruction prefix — passages and
    # queries are embedded differently on purpose (that's how BGE was trained).
    vector = list(_embedder().query_embed(query))[0]
    res = _client().query_points(
        collection_name=settings.collection,
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
