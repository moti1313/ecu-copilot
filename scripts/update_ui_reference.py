"""Refresh the dashboard's read-only specification excerpts from the canonical documents.

Run after changing TS-DCU-EOL.md or its machine-readable specification:
    python scripts/update_ui_reference.py
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_reference(root: Path = ROOT) -> dict:
    spec = json.loads((root / "docs/spec/TS-DCU-EOL.json").read_text(encoding="utf-8"))
    markdown = (root / "docs/TS-DCU-EOL.md").read_text(encoding="utf-8")
    headings = list(re.finditer(r"^#{2,3} ([0-9]+(?:\.[0-9]+)*)\.?\s+(.+)$", markdown, re.M))
    sections = {}
    for i, heading in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(markdown)
        sections[heading.group(1)] = {"title": heading.group(2), "text": markdown[heading.end() : end].strip()}
    return {"spec": spec, "sections": sections}


def main() -> None:
    path = ROOT / "src/ecu_copilot/copilot/static/index.html"
    html = path.read_text(encoding="utf-8")
    reference = json.dumps(build_reference(), ensure_ascii=False).replace("<", "\\u003c")
    html, count = re.subn(
        r'(<script type="application/json" id="productionReference">).*?(</script>)',
        lambda match: match.group(1) + reference + match.group(2),
        html,
        flags=re.S,
    )
    if count != 1:
        raise RuntimeError("Expected exactly one productionReference block in the dashboard")
    path.write_text(html, encoding="utf-8")
    print("Updated dashboard specification reference from canonical documents.")


if __name__ == "__main__":
    main()
