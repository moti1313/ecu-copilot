"""Build and query the document index.

Two retrievers, fused:
- vector search (ChromaDB + fastembed) for meaning: "Warum steigt der Ruhestrom?" finds §7.3
  of the MCU datasheet although the words differ.
- BM25 for exact tokens: "E-204", "HB4821", "J3" - embeddings are weak on part numbers.
Reciprocal rank fusion (RRF) merges the two ranked lists without score calibration.

RAG_MODE=bm25 skips the embedding model entirely (tests, CI, air-gapped machines).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

from .. import config
from .chunking import Chunk, chunk_directory

COLLECTION = "ecu_docs"
_TOKEN = re.compile(r"[a-zA-Z0-9äöüÄÖÜß§\-\.]+")


def _tokenize(text: str) -> list[str]:
    return [t.lower().strip(".") for t in _TOKEN.findall(text)]


class DocumentIndex:
    def __init__(self, data_dir: Path | None = None, mode: str | None = None, embedding_model: str | None = None):
        self.data_dir = data_dir or config.DATA_DIR
        self.mode = mode or config.RAG_MODE
        self.embedding_model = embedding_model or config.EMBEDDING_MODEL
        self.chunks_file = self.data_dir / "chunks.json"
        self.chroma_dir = self.data_dir / "chroma"
        self._chunks: list[Chunk] = []
        self._bm25: BM25Okapi | None = None
        self._collection = None
        self._embedder = None

    # --- build ----------------------------------------------------------------------
    def build(self, docs_dir: Path | None = None) -> int:
        chunks = chunk_directory(docs_dir or config.DOCS_DIR)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.chunks_file.write_text(json.dumps([c.__dict__ for c in chunks], ensure_ascii=False, indent=1))
        self._chunks = chunks
        self._bm25 = BM25Okapi([_tokenize(c.text) for c in chunks])
        if self.mode == "hybrid":
            col = self._chroma()
            if col.count():
                col.delete(ids=col.get()["ids"])
            vectors = list(self._embed([c.text for c in chunks]))
            col.add(
                ids=[c.chunk_id for c in chunks],
                embeddings=vectors,
                documents=[c.text for c in chunks],
                metadatas=[{"doc_id": c.doc_id, "section": c.section, "title": c.title} for c in chunks],
            )
        return len(chunks)

    # --- load -----------------------------------------------------------------------
    def load(self) -> DocumentIndex:
        if not self.chunks_file.exists():
            raise FileNotFoundError(f"{self.chunks_file} missing - run `uv run python -m ecu_copilot.rag.ingest`")
        raw = json.loads(self.chunks_file.read_text())
        self._chunks = [Chunk(**c) for c in raw]
        self._bm25 = BM25Okapi([_tokenize(c.text) for c in self._chunks])
        if self.mode == "hybrid":
            self._chroma()
        return self

    @property
    def ready(self) -> bool:
        return bool(self._chunks)

    # --- search ---------------------------------------------------------------------
    def search(self, query: str, k: int | None = None) -> list[dict]:
        k = k or config.RAG_TOP_K
        if not self._chunks:
            self.load()
        by_id = {c.chunk_id: c for c in self._chunks}
        ranked: list[list[str]] = [self._bm25_rank(query, k * 3)]
        if self.mode == "hybrid":
            ranked.append(self._vector_rank(query, k * 3))

        # reciprocal rank fusion: score = sum 1 / (60 + rank)
        fused: dict[str, float] = {}
        for ranking in ranked:
            for rank, cid in enumerate(ranking):
                fused[cid] = fused.get(cid, 0.0) + 1.0 / (60 + rank)
        top = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:k]
        return [
            {
                "citation": by_id[cid].citation(),
                "doc_id": by_id[cid].doc_id,
                "section": by_id[cid].section,
                "title": by_id[cid].title,
                "score": round(score, 4),
                "text": by_id[cid].text,
            }
            for cid, score in top
        ]

    def _bm25_rank(self, query: str, n: int) -> list[str]:
        assert self._bm25 is not None
        scores = self._bm25.get_scores(_tokenize(query))
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [self._chunks[i].chunk_id for i in order[:n] if scores[i] > 0]

    def _vector_rank(self, query: str, n: int) -> list[str]:
        col = self._chroma()
        vec = next(iter(self._embed([query])))
        res = col.query(query_embeddings=[vec], n_results=min(n, col.count()))
        return res["ids"][0]

    # --- backends -------------------------------------------------------------------
    def _chroma(self):
        if self._collection is None:
            import chromadb  # imported lazily: heavy, and not needed in bm25 mode

            client = chromadb.PersistentClient(path=str(self.chroma_dir))
            self._collection = client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})
        return self._collection

    def _embed(self, texts: list[str]):
        if self._embedder is None:
            from fastembed import TextEmbedding

            self._embedder = TextEmbedding(model_name=self.embedding_model, cache_dir=str(self.data_dir / "models"))
        return ([float(x) for x in v] for v in self._embedder.embed(texts))
