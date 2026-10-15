"""CLI: build the document index.   uv run python -m ecu_copilot.rag.ingest"""

from __future__ import annotations

import sys
import time

from .. import config
from .index import DocumentIndex


def main() -> int:
    t0 = time.perf_counter()
    index = DocumentIndex()
    print(f"[ingest] docs={config.DOCS_DIR} mode={index.mode} data={index.data_dir}")
    n = index.build()
    print(f"[ingest] {n} chunks indexed in {time.perf_counter() - t0:.1f}s")
    for hit in index.search("quiescent current limit variant B", k=3):
        print(f"  smoke test -> {hit['citation']}  (score {hit['score']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
