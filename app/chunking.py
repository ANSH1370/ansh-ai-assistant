"""Markdown-header-aware chunking.

The corpus files are written with self-contained `##` sections, so the natural
chunk is one section. Each chunk is prefixed with the document title and
section heading — retrieval sees "Project — CareerMatch AI / How it works: ..."
instead of a context-free paragraph.
"""

import re
from dataclasses import dataclass, field

# Rough token budget per chunk. Sections in this corpus are ~100-250 tokens;
# the split below only kicks in if a section grows past this.
MAX_CHARS = 1800


@dataclass
class Chunk:
    text: str
    title: str
    section: str
    doc_type: str
    url: str
    metadata: dict = field(default_factory=dict)


def split_sections(body: str) -> list[tuple[str, str]]:
    """Split a markdown body into (heading, content) pairs on `##` headers."""
    parts = re.split(r"^## +(.+)$", body, flags=re.MULTILINE)
    sections = []
    # parts[0] is any preamble before the first header — keep it if non-trivial
    if parts[0].strip():
        sections.append(("Overview", parts[0].strip()))
    for i in range(1, len(parts) - 1, 2):
        heading, content = parts[i].strip(), parts[i + 1].strip()
        if content:
            sections.append((heading, content))
    return sections


def chunk_document(body: str, title: str, doc_type: str, url: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    for heading, content in split_sections(body):
        # Oversized section → split on paragraph boundaries
        pieces = [content]
        if len(content) > MAX_CHARS:
            paras = content.split("\n\n")
            pieces, current = [], ""
            for p in paras:
                if len(current) + len(p) > MAX_CHARS and current:
                    pieces.append(current.strip())
                    current = p
                else:
                    current = f"{current}\n\n{p}" if current else p
            if current.strip():
                pieces.append(current.strip())

        for piece in pieces:
            chunks.append(
                Chunk(
                    text=f"{title} — {heading}\n\n{piece}",
                    title=title,
                    section=heading,
                    doc_type=doc_type,
                    url=url,
                )
            )
    return chunks
