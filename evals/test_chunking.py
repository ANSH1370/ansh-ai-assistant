"""Unit tests for the chunker — fast, no models, no network."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import frontmatter  # noqa: E402

from app.chunking import MAX_CHARS, chunk_document, split_sections  # noqa: E402


def test_sections_split_on_h2():
    body = "intro text\n\n## First\ncontent one\n\n## Second\ncontent two"
    sections = split_sections(body)
    assert [s[0] for s in sections] == ["Overview", "First", "Second"]


def test_chunks_carry_title_and_metadata():
    chunks = chunk_document("## About\nSome text", "Doc Title", "project", "https://x")
    assert len(chunks) == 1
    c = chunks[0]
    assert c.text.startswith("Doc Title — About")
    assert (c.title, c.doc_type, c.url) == ("Doc Title", "project", "https://x")


def test_long_sections_get_split():
    para = "word " * 120  # ~600 chars
    body = "## Big\n" + "\n\n".join([para] * 6)  # ~3.6k chars > MAX_CHARS
    chunks = chunk_document(body, "T", "project", "u")
    assert len(chunks) > 1
    assert all(len(c.text) <= MAX_CHARS + 200 for c in chunks)


def test_real_corpus_chunks_are_reasonable():
    corpus = ROOT / "corpus"
    total = 0
    for f in corpus.glob("*.md"):
        doc = frontmatter.load(f)
        chunks = chunk_document(doc.content, str(doc.get("title")), str(doc.get("type")), str(doc.get("url")))
        assert chunks, f"{f.name} produced no chunks"
        assert all(c.url for c in chunks), f"{f.name} missing url frontmatter"
        total += len(chunks)
    assert 20 <= total <= 120, f"unexpected corpus size: {total} chunks"
