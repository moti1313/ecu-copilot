"""The production viewer must not silently show limits or excerpts from an older spec."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_production_reference_matches_current_specification():
    html = (ROOT / "src/ecu_copilot/copilot/static/index.html").read_text(encoding="utf-8")
    match = re.search(r'<script type="application/json" id="productionReference">(.*?)</script>', html, re.S)
    assert match, "Missing production reference"
    reference = json.loads(match.group(1))
    spec = json.loads((ROOT / "docs/spec/TS-DCU-EOL.json").read_text(encoding="utf-8"))
    assert reference["spec"] == spec, "Refresh with: python scripts/update_ui_reference.py"
    markdown = (ROOT / "docs/TS-DCU-EOL.md").read_text(encoding="utf-8")
    for section in ("3", "4.1", "4.2", "4.3", "4.4", "4.5", "5", "6.1"):
        excerpt = reference["sections"][section]
        assert excerpt["text"] and excerpt["text"] in markdown, f"Stale or missing excerpt {section}"
        assert re.search(rf"^#{{2,3}} {re.escape(section)}\.?\s+{re.escape(excerpt['title'])}$", markdown, re.M)
