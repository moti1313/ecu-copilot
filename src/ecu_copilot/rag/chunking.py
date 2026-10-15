"""Markdown -> chunks. Sections are the natural unit of an engineering document:
a limit table, a failure-code table, a procedure step. Each chunk keeps the
document id and the section heading, so the agent can cite "TS-DCU-EOL §4.2".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

MAX_WORDS = 320  # ~450 tokens; bigger sections are split into overlapping windows
OVERLAP_WORDS = 50

_FRONT_MATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)
_HEADING = re.compile(r"^(#{1,3})\s+(.*)$", re.M)


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    title: str
    section: str
    text: str
    meta: dict = field(default_factory=dict)

    def citation(self) -> str:
        return f"{self.doc_id} §{self.section}" if self.section else self.doc_id


def parse_front_matter(text: str) -> tuple[dict, str]:
    m = _FRONT_MATTER.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, text[m.end() :]


def split_sections(body: str) -> list[tuple[str, str]]:
    """Return (heading, text) pairs. Text before the first heading is dropped (it is the title)."""
    matches = list(_HEADING.finditer(body))
    sections: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        level = len(m.group(1))
        if level == 1:
            continue  # document title line
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        text = body[start:end].strip()
        if text:
            sections.append((m.group(2).strip(), text))
    return sections


def _windows(words: list[str]) -> list[list[str]]:
    if len(words) <= MAX_WORDS:
        return [words]
    out, start = [], 0
    while start < len(words):
        out.append(words[start : start + MAX_WORDS])
        if start + MAX_WORDS >= len(words):
            break
        start += MAX_WORDS - OVERLAP_WORDS
    return out


def chunk_document(path: Path) -> list[Chunk]:
    raw = path.read_text(encoding="utf-8")
    meta, body = parse_front_matter(raw)
    doc_id = meta.get("doc_id", path.stem)
    title = meta.get("title", path.stem)
    chunks: list[Chunk] = []
    for heading, text in split_sections(body):
        first = heading.split(" ", 1)[0].rstrip(".")
        section_no = first if re.match(r"^\d+(\.\d+)*$", first) else ""
        for i, words in enumerate(_windows(text.split())):
            suffix = f"-{i}" if i else ""
            chunk_text = f"{title}\n{heading}\n\n{' '.join(words)}"
            chunks.append(
                Chunk(
                    chunk_id=f"{doc_id}:{section_no or heading[:20]}{suffix}",
                    doc_id=doc_id,
                    title=title,
                    section=section_no or heading,
                    text=chunk_text,
                    meta={"heading": heading, "revision": meta.get("revision", ""), "date": meta.get("date", "")},
                )
            )
    return chunks


def chunk_directory(docs_dir: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(docs_dir.glob("*.md")):
        chunks.extend(chunk_document(path))
    return chunks
