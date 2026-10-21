"""Build the curated source distribution (the hand-over copy for readers outside the project).

Why a script: the 2026-10-19 hand-over ZIP was assembled by hand. This makes the same rules repeatable:
  - copy an explicit allow-list from the working tree (code, tests, evals, synthetic docs, selected design docs);
  - overlay the curated reader-facing documents from dist/overrides/ (English summaries written for the
    stand-alone copy; the working-tree originals stay the project's internal documents);
  - exclude Git history, private notes, speaker notes, STATUS/AUDIT/RESEARCH, raw run archives, env files,
    caches and this dist/ folder itself;
  - scan the result for credentials, write DISTRIBUTION.md and SHA256SUMS, zip it;
  - with --verify: unpack into an empty temp dir and run `uv sync --frozen`, ruff and the offline tests there.

    uv run python scripts/make_distribution.py --out ~/AMK            # build ZIP next to the repo
    uv run python scripts/make_distribution.py --out ~/AMK --verify   # ... and check it in a fresh directory
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERRIDES = ROOT / "dist" / "overrides"
NAME = "ecu-copilot"

INCLUDE_FILES = [
    "README.md",
    "pyproject.toml",
    "uv.lock",
    ".python-version",
    "Dockerfile",
    "docker-compose.yml",
    ".dockerignore",
    ".gitignore",
    ".env.example",
    ".gitlab-ci.yml",
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
    "docker-compose.release.yml",
    "docker-compose.monitoring.yml",
    "scripts/update_ui_reference.py",  # build_presentation.py needs matplotlib (not a project dependency) - kept internal
    "design/ARCHITECTURE_CURRENT.md",
    "design/CONCEPT.md",
    "design/RESULTS.md",
    "design/RUN4_REVIEW.md",
    "design/presentation/README.md",
    "design/presentation/RECHERCHE.md",
    "design/presentation/ECU-Copilot-Praesentation.pdf",
    "design/presentation/Uebersicht.png",
]
INCLUDE_TREES = ["src", "tests", "evals", "docs", "design/presentation/diagrams", "monitoring"]
EXCLUDE_DIR_NAMES = {"__pycache__", ".pytest_cache", ".ruff_cache", ".venv", ".git", ".chroma"}
EXCLUDE_SUFFIXES = {".pyc", ".swp"}
# never ship (listed for the record, the allow-list already keeps them out)
NEVER = [
    "design/notes",
    "design/STATUS.md",
    "design/AUDIT.md",
    "design/RESEARCH.md",
    "design/ARCHITECTURE.md",
    "design/PRODUCTION_VIEW.md",
    "design/presentation/SPRECHTEXT.md",
    "design/presentation/Live.html",
    "design/presentation/manifest.json",
    "data",
    "dist",
    ".env",
    ".env.save",
    ".env.bak",
]
SECRET_PATTERNS = [r"apikey_[0-9a-f]{10,}", r"sk-[A-Za-z0-9_-]{20,}", r"AKIA[0-9A-Z]{16}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"]


def git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def iter_sources() -> list[Path]:
    files: list[Path] = []
    for rel in INCLUDE_FILES:
        p = ROOT / rel
        if not p.exists():
            print(f"  fehlt (übersprungen): {rel}")
            continue
        files.append(p)
    for tree in INCLUDE_TREES:
        for p in sorted((ROOT / tree).rglob("*")):
            if p.is_dir():
                continue
            if any(part in EXCLUDE_DIR_NAMES for part in p.relative_to(ROOT).parts) or p.suffix in EXCLUDE_SUFFIXES:
                continue
            files.append(p)
    return files


def build(stage: Path) -> tuple[list[str], list[str]]:
    """Copy allow-listed files, then overlay dist/overrides. Returns (shipped paths, overridden paths)."""
    dest_root = stage / NAME
    dest_root.mkdir(parents=True)
    shipped: list[str] = []
    for src in iter_sources():
        rel = src.relative_to(ROOT)
        dst = dest_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        shipped.append(str(rel))
    overridden: list[str] = []
    for ov in sorted(OVERRIDES.rglob("*")):
        if ov.is_file():
            rel = ov.relative_to(OVERRIDES)
            dst = dest_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ov, dst)
            overridden.append(str(rel))
            if str(rel) not in shipped:
                shipped.append(str(rel))
    return sorted(set(shipped)), overridden


def scan_secrets(dest_root: Path) -> list[str]:
    hits = []
    pat = re.compile("|".join(SECRET_PATTERNS))
    for p in dest_root.rglob("*"):
        if p.is_file() and p.suffix not in {".png", ".pdf", ".svg"}:
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if pat.search(text):
                hits.append(str(p.relative_to(dest_root)))
    return hits


def write_manifest(dest_root: Path, overridden: list[str], base_commit: str, dirty: bool) -> None:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    (dest_root / "DISTRIBUTION.md").write_text(
        f"""# Source distribution

Prepared {today} from local source commit `{base_commit or "unknown"}`{" plus uncommitted working-tree changes" if dirty else ""}.
Application code, tests, synthetic engineering documents and evaluation scripts are byte-identical to the
source working tree. The following reader-facing documents are curated for this stand-alone copy and differ
from the project's internal versions: {", ".join(f"`{o}`" for o in overridden)}.

Not included: Git metadata and history, raw benchmark run archives (`data/`), environment files, private
notes, speaker notes, internal status documents, caches and installed dependencies. `.env.example` contains
placeholders only. `SHA256SUMS` lists this distribution's file contents. This is a source snapshot; it does
not claim that the original benchmark used a clean checkout or that its exact historical state can be
reconstructed (see RUN4_REVIEW.md §6).

Built by `scripts/make_distribution.py` (allow-list, overlays, credential scan, checksums).
""",
        encoding="utf-8",
    )
    lines = []
    for p in sorted(dest_root.rglob("*")):
        if p.is_file() and p.name != "SHA256SUMS":
            lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(dest_root)}")
    (dest_root / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_zip(stage: Path, out: Path) -> None:
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted((stage / NAME).rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(stage))


def verify(zip_path: Path, docker: bool) -> int:
    """Fresh-directory check: unpack, sync, lint, offline tests (and optionally the Docker build)."""
    with tempfile.TemporaryDirectory(prefix="ecu-dist-check-") as td:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(td)
        root = Path(td) / NAME
        env = {**os.environ, "RAG_MODE": "bm25", "PYTHONPATH": ""}
        env.pop("VIRTUAL_ENV", None)
        steps = [
            ["uv", "sync", "--frozen"],
            ["uv", "run", "ruff", "check", "."],
            ["uv", "run", "ruff", "format", "--check", "."],
            ["uv", "run", "pytest", "-q"],
        ]
        if docker:
            steps.append(["docker", "build", "-t", "ecu-copilot-dist-check", "."])
        for cmd in steps:
            print(f"  $ {' '.join(cmd)}")
            r = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True)
            tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
            for line in tail:
                print(f"    {line}")
            if r.returncode != 0:
                print(f"  FEHLGESCHLAGEN: {' '.join(cmd)} (exit {r.returncode})")
                return r.returncode
    print("  Frischprüfung bestanden.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT.parent), help="directory for the ZIP (default: next to the repo)")
    ap.add_argument("--verify", action="store_true", help="unpack into a temp dir and run sync, lint, tests")
    ap.add_argument("--docker", action="store_true", help="with --verify: also build the Docker image")
    args = ap.parse_args()

    base_commit = git("rev-parse", "HEAD")
    dirty = bool(git("status", "--porcelain"))
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    out = Path(args.out).expanduser() / f"{NAME}-share-{today}.zip"

    with tempfile.TemporaryDirectory(prefix="ecu-dist-") as td:
        stage = Path(td)
        shipped, overridden = build(stage)
        dest_root = stage / NAME
        for never in NEVER:
            if (dest_root / never).exists():
                print(f"FEHLER: ausgeschlossener Pfad im Paket: {never}")
                return 2
        hits = scan_secrets(dest_root)
        if hits:
            print("FEHLER: mögliche Zugangsdaten in:", ", ".join(hits))
            return 2
        write_manifest(dest_root, overridden, base_commit, dirty)
        make_zip(stage, out)
    print(f"Paket: {out} ({out.stat().st_size // 1024} KiB, {len(shipped) + 2} Dateien)")
    print(f"Quelle: {base_commit[:7] or '?'}{' + uncommitted' if dirty else ''} · Overrides: {len(overridden)}")
    for o in overridden:
        wt = ROOT / o
        if wt.exists() and wt.read_bytes() != (OVERRIDES / o).read_bytes():
            print(f"  Hinweis: {o} weicht vom Arbeitsbaum ab (kuratiert) - bei inhaltlichen Änderungen Override nachziehen")
    if args.verify:
        return verify(out, args.docker)
    return 0


if __name__ == "__main__":
    sys.exit(main())
