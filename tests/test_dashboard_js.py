"""Frontend regression for the dashboard's API-key handling, executed with node (review R2/R3)."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_dashboard_auth_block():
    r = subprocess.run(
        ["node", str(ROOT / "tests/js/auth_block.test.js"), str(ROOT / "src/ecu_copilot/copilot/static/index.html")],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "auth block ok" in r.stdout
