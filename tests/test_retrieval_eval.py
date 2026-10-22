"""Retrieval evaluation: scoring functions and a golden set that must stay in sync with the chunked documents."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ecu_copilot import config
from ecu_copilot.rag.chunking import chunk_directory
from evals.retrieval_eval import aggregate, evaluate, load_golden, score_ranking


def test_score_ranking_metrics():
    r = score_ranking(["A", "B", "C", "D", "E"], ["B", "E"])
    assert r["rr"] == 0.5 and r["hit@1"] == 0.0 and r["hit@3"] == 1.0
    assert r["recall@3"] == 0.5 and r["recall@5"] == 1.0
    assert score_ranking(["X"], ["B"])["rr"] == 0.0
    agg = aggregate([score_ranking(["B"], ["B"]), score_ranking(["X", "B"], ["B"])])
    assert agg["mrr"] == 0.75 and agg["hit@1"] == 0.5 and agg["n"] == 2


def test_golden_citations_exist_in_documents():
    cits = set()
    for c in chunk_directory(config.DOCS_DIR):
        cits.add(c.citation() if callable(getattr(c, "citation", None)) else c.citation)
    items = load_golden()
    assert len(items) >= 15
    missing = [(it["id"], c) for it in items for c in it["relevant"] if c not in cits]
    assert not missing, missing


def test_bm25_reaches_a_minimum_on_the_golden_set(bm25_index):
    """A floor, not a target: keeps a retrieval regression from passing unnoticed. German queries are allowed to miss."""
    rows, agg = evaluate(bm25_index, load_golden())
    english = [r for r in rows if r["id"] not in ("q19", "q20")]
    assert aggregate(english)["hit@5"] >= 0.8, [(r["id"], r["top"]) for r in english if not r["hit@5"]]
    assert agg["mrr"] > 0.5
