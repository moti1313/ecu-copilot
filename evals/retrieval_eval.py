"""Retrieval evaluation - offline, no model calls. Measures whether the document search returns the sections an
engineer needs, independent of what the agent then does with them.

    RAG_MODE=bm25 uv run python evals/retrieval_eval.py            # BM25 only (CI mode, no downloads)
    RAG_MODE=hybrid uv run python evals/retrieval_eval.py          # BM25 + local embeddings (downloads the model once)

Metrics per golden query: hit@k (any relevant section in the top k), recall@k (share of relevant sections in the
top k), reciprocal rank of the first relevant section; averaged over the set. The golden set is small and was
written by the author from the synthetic documents, so it measures the search on these documents, not retrieval
quality in general. German queries (q19, q20) show the gap of a keyword-only index on English documents.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

GOLDEN = ROOT / "evals" / "retrieval_golden.json"
KS = (1, 3, 5)


def load_golden(path: Path = GOLDEN) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["items"]


def score_ranking(ranked: list[str], relevant: list[str], ks=KS) -> dict:
    """ranked: citations in result order; relevant: citations that answer the query."""
    rel = set(relevant)
    out: dict = {}
    first = next((i + 1 for i, c in enumerate(ranked) if c in rel), None)
    out["rr"] = 1.0 / first if first else 0.0
    for k in ks:
        top = ranked[:k]
        found = sum(1 for c in rel if c in top)
        out[f"hit@{k}"] = 1.0 if found else 0.0
        out[f"recall@{k}"] = found / len(rel) if rel else 0.0
    return out


def aggregate(rows: list[dict], ks=KS) -> dict:
    n = max(1, len(rows))
    agg = {"n": len(rows), "mrr": sum(r["rr"] for r in rows) / n}
    for k in ks:
        agg[f"hit@{k}"] = sum(r[f"hit@{k}"] for r in rows) / n
        agg[f"recall@{k}"] = sum(r[f"recall@{k}"] for r in rows) / n
    return agg


def evaluate(index, items: list[dict], k_max: int = max(KS)) -> tuple[list[dict], dict]:
    rows = []
    for it in items:
        hits = index.search(it["query"], k=k_max)
        ranked = [h["citation"] for h in hits]
        r = score_ranking(ranked, it["relevant"])
        rows.append({"id": it["id"], "query": it["query"], "top": ranked[:3], **r})
    return rows, aggregate(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None, help="write per-query rows and the aggregate to this file")
    args = ap.parse_args()
    from ecu_copilot import config
    from ecu_copilot.rag.index import DocumentIndex

    tmp = Path(tempfile.mkdtemp(prefix="retrieval-eval-"))
    try:
        index = DocumentIndex(data_dir=tmp)
    except TypeError:
        index = DocumentIndex()
    index.build()
    index.load()
    rows, agg = evaluate(index, load_golden())
    mode = os.environ.get("RAG_MODE", getattr(config, "RAG_MODE", "?"))
    print(f"Retrieval-Evaluation · Modus {mode} · {agg['n']} Fragen · Chunks aus {config.DOCS_DIR}")
    print(f"{'id':<5}{'hit@1':>6}{'hit@3':>6}{'hit@5':>6}{'rec@5':>7}{'RR':>6}  top-3")
    for r in rows:
        print(
            f"{r['id']:<5}{r['hit@1']:>6.0f}{r['hit@3']:>6.0f}{r['hit@5']:>6.0f}{r['recall@5']:>7.2f}{r['rr']:>6.2f}  {', '.join(r['top'])}"
        )
    print(
        f"\nMRR {agg['mrr']:.3f} · hit@1 {agg['hit@1']:.2f} · hit@3 {agg['hit@3']:.2f} · hit@5 {agg['hit@5']:.2f} · recall@5 {agg['recall@5']:.2f}"
    )
    if args.json:
        Path(args.json).write_text(
            json.dumps({"mode": mode, "aggregate": agg, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
