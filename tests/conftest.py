"""Shared fixtures. No network, no API key: the LLM is faked, the twin runs in-process."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ecu_copilot.rag.index import DocumentIndex
from ecu_copilot.twin.simulator import Simulator

DOCS_DIR = Path(__file__).resolve().parents[1] / "docs"


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 10, 15, 10, 0, tzinfo=UTC)


@pytest.fixture
def sim(now: datetime) -> Simulator:
    s = Simulator(seed=7)
    s.seed_history(minutes=20, interval_s=1.5, now=now)
    return s


@pytest.fixture
def bm25_index(tmp_path: Path) -> DocumentIndex:
    index = DocumentIndex(data_dir=tmp_path, mode="bm25")
    index.build(DOCS_DIR)
    return index


@pytest.fixture
def twin_client() -> TestClient:
    from ecu_copilot.twin import api

    with TestClient(api.app) as client:
        yield client
