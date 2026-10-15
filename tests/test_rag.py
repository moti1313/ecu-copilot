from pathlib import Path

from ecu_copilot.rag.chunking import chunk_document
from tests.conftest import DOCS_DIR


def test_chunks_carry_doc_id_and_section_number():
    chunks = chunk_document(DOCS_DIR / "TS-DCU-EOL.md")
    citations = {c.citation() for c in chunks}
    assert "TS-DCU-EOL §4.2" in citations
    assert "TS-DCU-EOL §5" in citations
    assert all(c.text.startswith("End-of-Line Test Specification") for c in chunks)


def test_every_document_is_indexed(bm25_index):
    doc_ids = {c.doc_id for c in bm25_index._chunks}
    assert doc_ids == {p.stem for p in Path(DOCS_DIR).glob("*.md")}


def test_bm25_finds_exact_identifiers(bm25_index):
    assert bm25_index.search("E-120 root cause", k=3)[0]["doc_id"] in {"FMEA-DCU-B2", "TS-DCU-EOL", "WI-EOL-PSEUDO"}
    assert bm25_index.search("HB4821 last time buy", k=1)[0]["doc_id"] == "PCN-2026-017"
    assert bm25_index.search("8D report minimum content", k=1)[0]["citation"] == "WI-EOL-PSEUDO §5"


def test_search_result_shape(bm25_index):
    hit = bm25_index.search("background noise acoustic test", k=1)[0]
    assert set(hit) == {"citation", "doc_id", "section", "title", "score", "text"}
    assert hit["citation"] == "TS-DCU-EOL §6.1"
