"""Load the machine-readable test specification (generated from the markdown, checked by a test)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .. import config

SPEC_DIR = config.DOCS_DIR / "spec"


@lru_cache(maxsize=8)
def load_spec(doc_id: str = "TS-DCU-EOL", revision: str | None = None) -> dict:
    """Current revision by default; `revision="C"` loads docs/spec/TS-DCU-EOL.rev-C.json if present."""
    path = SPEC_DIR / (f"{doc_id}.rev-{revision}.json" if revision else f"{doc_id}.json")
    if not path.exists():
        raise FileNotFoundError(f"specification file missing: {path}")
    return json.loads(Path(path).read_text(encoding="utf-8"))


def limit(spec: dict, variant: str, key: str) -> float:
    return float(spec["limits"][variant][key])


def validity_window(spec: dict, measurement: str) -> dict:
    return spec["validity"][measurement]
