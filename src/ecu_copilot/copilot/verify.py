"""Evidence verification - runs after the model, before the answer. No LLM.

Two separate checks with separate names, because they answer different questions:
- provenance: does this evidence item really come from where it says? A live ref must point to a tool
  call of this run, the field must exist in that call's output for exactly the stated scope, and the
  value must match. A document ref must name an existing document, revision and section.
- support: does the referenced value/section actually support the statement? For documents this is
  a keyword-overlap heuristic (and labelled as such); for live refs it is only checked for simple
  comparisons against specification limits, otherwise "not_checked".

Why: the most frequent failure of RCA agents is a coherent story the data does not support
(71 % of runs in arXiv 2602.09937). Prompting does not fix it; checking does.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .consistency import ConsistencyFlag, check_consistency, summarize as summarize_consistency

_CITE = re.compile(r"^\s*([A-Z][A-Z0-9-]+?)\s*(?:Rev\.?\s*([A-Z0-9]+))?\s*(?:§\s*|item\s+|section\s+)?([0-9][0-9.]*)?\s*$", re.I)
_PATH_STEP = re.compile(r"^([A-Za-z0-9_\- ]+)(?:\[(.*)\])?$")
_TOKEN = re.compile(r"[A-Za-z0-9äöüÄÖÜß][A-Za-z0-9äöüÄÖÜß\-\.]{3,}|\d+(?:[.,]\d+)?")


@dataclass
class ItemVerdict:
    index: int
    source_type: str
    provenance: str  # verified | not_found | wrong_scope | value_mismatch | unknown_section | superseded | no_ref
    support: str  # supported | weak | not_checked | contradicted
    detail: str = ""


@dataclass
class Verification:
    items: list[ItemVerdict] = field(default_factory=list)
    consistency: list[ConsistencyFlag] = field(default_factory=list)  # CONCEPT §11 - marks, never corrections

    def summary(self) -> dict:
        live = [i for i in self.items if i.source_type == "live"]
        docs = [i for i in self.items if i.source_type == "document"]

        def rate(xs, attr, ok):
            n = sum(1 for x in xs if getattr(x, attr) in ok)
            return {"ok": n, "total": len(xs)}

        return {
            "provenance": {"live": rate(live, "provenance", {"verified"}), "docs": rate(docs, "provenance", {"verified"})},
            "support": {"live": rate(live, "support", {"supported"}), "docs": rate(docs, "support", {"supported"})},
            "flags": [f"evidence {i.index + 1}: {i.provenance}" for i in self.items if i.provenance != "verified"],
            "items": [i.__dict__ for i in self.items],
            "consistency": summarize_consistency(self.consistency),
            "method": "provenance: ref vs tool outputs / doc index; support: spec comparison (live), keyword overlap (docs); consistency: CONCEPT §11",
        }


# ---------------------------------------------------------------------------------------------
def resolve_path(data: Any, path: str) -> Any:
    """Resolve 'groups[station=2,variant=B].failure_rate_pct' or 'codes.E-204.invalid_per_spec' or 'top.lift'.
    A step with [k=v,...] selects the first element of a list whose fields match; [n] indexes a list."""
    cur = data
    for raw in _split_path(path):
        m = _PATH_STEP.match(raw.strip())
        if not m:
            raise KeyError(path)
        name, selector = m.group(1).strip(), m.group(2)
        if isinstance(cur, dict):
            if name not in cur:
                raise KeyError(name)
            cur = cur[name]
        else:
            raise KeyError(name)
        if selector is not None:
            if not isinstance(cur, list):
                raise KeyError(f"{name} is not a list")
            if selector.strip().isdigit():
                cur = cur[int(selector)]
            else:
                conds = dict(kv.split("=", 1) for kv in selector.split(","))
                match = next(
                    (e for e in cur if isinstance(e, dict) and all(str(e.get(k.strip())) == v.strip() for k, v in conds.items())), None
                )
                if match is None:
                    raise LookupError(f"no element matches [{selector}]")
                cur = match
    return cur


def _split_path(path: str) -> list[str]:
    out, depth, buf = [], 0, ""
    for ch in path:
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        if ch == "." and depth == 0:
            out.append(buf)
            buf = ""
        else:
            buf += ch
    if buf:
        out.append(buf)
    return out


def _values_match(expected: Any, actual: Any) -> bool:
    if isinstance(expected, bool) or isinstance(actual, bool):
        return str(expected).lower() == str(actual).lower()
    try:
        e, a = float(expected), float(actual)
    except (TypeError, ValueError):
        return str(expected).strip().lower() == str(actual).strip().lower()
    return abs(e - a) <= max(0.01 * abs(a), 0.051)  # 1 % or rounding to one decimal


def _scope_matches(ref: dict, tool_input: dict, output: Any) -> bool:
    """The ref's station/variant/window must be the scope the tool was called with (or selected in the path)."""
    scope = output.get("scope") if isinstance(output, dict) else None
    for key, ref_key in (("station", "station"), ("variant", "variant"), ("window_minutes", "window_minutes")):
        if ref.get(ref_key) in (None, ""):
            continue
        called = (scope or {}).get(key) if scope else tool_input.get(key if key != "window_minutes" else "minutes")
        if called in (None, "") and key != "window_minutes":
            continue  # tool was called for all stations/variants; the path selector must pick the group (checked by resolve)
        if called is not None and str(called) != str(ref[ref_key]):
            return False
    return True


def verify_live(ref: dict, tool_calls: list) -> tuple[str, str]:
    idx = ref.get("tool_call")
    if not isinstance(idx, int) or idx < 1 or idx > len(tool_calls):
        return "no_ref", "tool_call index missing or out of range"
    call = tool_calls[idx - 1]
    try:
        output = json.loads(call.output or "")
    except (TypeError, ValueError):
        return "not_found", "tool output is not JSON"
    if isinstance(output, dict) and "error" in output:
        return "not_found", "referenced tool call returned an error"
    if not _scope_matches(ref, call.input, output):
        return "wrong_scope", f"tool {call.name} was called for {call.input}, ref claims {ref}"
    field = ref.get("field") or ""
    # a selector inside the path ("groups[station=1,variant=A]") must agree with the claimed scope too
    for key in ("station", "variant"):
        m = re.search(rf"\[[^\]]*\b{key}=([^,\]]+)", field)
        if m and ref.get(key) not in (None, "") and str(ref[key]) != m.group(1).strip():
            return "wrong_scope", f"path selects {key}={m.group(1)} but ref claims {key}={ref[key]}"
    try:
        actual = resolve_path(output, field)
    except (KeyError, LookupError, IndexError, TypeError, ValueError) as e:
        return "not_found", f"field '{field}' not in output of {call.name}: {e}"
    if "value" in ref and ref["value"] is not None and not _values_match(ref["value"], actual):
        return "value_mismatch", f"ref says {ref['value']}, tool says {actual}"
    return "verified", f"{call.name}: {field} = {actual}"


def parse_citation(text: str) -> tuple[str | None, str | None, str | None]:
    m = _CITE.match(text or "")
    if not m:
        return None, None, None
    return m.group(1).upper(), (m.group(2) or None), (m.group(3).rstrip(".") if m.group(3) else None)


def verify_doc(ref: dict, citation: str, chunks: list) -> tuple[str, str, str | None]:
    """Returns (provenance, detail, chunk_text)."""
    doc_id, revision, section = ref.get("doc_id"), ref.get("revision"), ref.get("section")
    if not doc_id:
        doc_id, revision, section = parse_citation(citation)
    if not doc_id:
        return "no_ref", "no document id", None
    doc_chunks = [c for c in chunks if c.doc_id.upper() == str(doc_id).upper()]
    if not doc_chunks:
        return "not_found", f"document {doc_id} not in index", None
    # normalise what models write: "§4.2", "section 4.2", "item 7", "Rev. D"
    sec = re.sub(r"^\s*(§|item|section|abschnitt|sec\.?)\s*", "", str(section), flags=re.I).strip().rstrip(".") if section else None
    revision = re.sub(r"^\s*rev(ision)?\.?\s*", "", str(revision), flags=re.I).strip() if revision else None
    hit = None
    if sec:
        hit = next((c for c in doc_chunks if c.section == sec or c.section.split(" ")[0].rstrip(".") == sec), None)
        if hit is None:
            return "unknown_section", f"{doc_id} has no section {sec}", None
    else:
        hit = doc_chunks[0]
    rev_actual = (hit.meta or {}).get("revision")
    status = (hit.meta or {}).get("status", "current")
    if status != "current":
        return "superseded", f"{doc_id} Rev. {rev_actual} is {status}", hit.text
    if revision and rev_actual and str(revision).upper() != str(rev_actual).upper():
        return "superseded", f"cited Rev. {revision}, current is Rev. {rev_actual}", hit.text
    return "verified", f"{doc_id} Rev. {rev_actual} §{hit.section}", hit.text


def support_doc(statement: str, chunk_text: str | None) -> tuple[str, str]:
    if not chunk_text:
        return "not_checked", ""
    tokens = {t.lower().replace(",", ".") for t in _TOKEN.findall(statement or "")}
    tokens = {
        t for t in tokens if t not in {"this", "that", "with", "from", "nach", "oder", "dass", "wird", "sind", "eine", "einer", "nicht"}
    }
    if not tokens:
        return "not_checked", "no checkable terms"
    text = chunk_text.lower().replace(",", ".")
    present = {t for t in tokens if t in text}
    share = len(present) / len(tokens)
    if share >= 0.5:
        return "supported", f"{len(present)}/{len(tokens)} terms found in the cited section"
    if share >= 0.25:
        return "weak", f"only {len(present)}/{len(tokens)} terms found in the cited section"
    return "weak", f"{len(present)}/{len(tokens)} terms found - the cited section may not support this statement"


def support_live(ref: dict, statement: str, spec: dict | None) -> tuple[str, str]:
    """Only simple comparisons against specification limits are checked deterministically."""
    if not spec or ref.get("value") is None:
        return "not_checked", ""
    field = str(ref.get("field") or "")
    s = (statement or "").lower()
    try:
        v = float(ref["value"])
    except (TypeError, ValueError):
        return "not_checked", ""
    variant = str(ref.get("variant") or "").upper()
    if "quiescent_current_ua" in field and variant in spec["limits"]:
        lim = spec["limits"][variant]["quiescent_max_ua"]
        says_above = any(w in s for w in ("über", "above", "oberhalb", "exceeds", ">"))
        says_below = any(w in s for w in ("unter", "below", "innerhalb", "within", "<"))
        if says_above and v <= lim:
            return "contradicted", f"statement says above limit but {v} ≤ {lim}"
        if says_below and v > lim:
            return "contradicted", f"statement says within limit but {v} > {lim}"
        if says_above or says_below:
            return "supported", f"{v} vs limit {lim}"
    if "board_temp_c" in field:
        lo, hi = spec["validity"]["board_temp_c"]["min"], spec["validity"]["board_temp_c"]["max"]
        says_out = any(w in s for w in ("außerhalb", "outside", "über", "above", "oberhalb", "ungültig", "invalid"))
        if says_out:
            return ("supported", f"{v} outside {lo}–{hi}") if not (lo <= v <= hi) else ("contradicted", f"{v} is inside {lo}–{hi}")
    return "not_checked", ""


def verify_report(report: dict | None, tool_calls: list, chunks: list, spec: dict | None) -> Verification:
    ver = Verification()
    if not report:
        return ver
    ver.consistency = check_consistency(report, tool_calls)
    for i, ev in enumerate(report.get("evidence") or []):
        ref = ev.get("ref") or {}
        st = ev.get("source_type")
        if st == "live":
            prov, detail = verify_live(ref, tool_calls)
            sup, sdetail = support_live(ref, ev.get("statement", ""), spec) if prov == "verified" else ("not_checked", "")
            ver.items.append(ItemVerdict(i, "live", prov, sup, f"{detail}; {sdetail}".strip("; ")))
        else:
            prov, detail, text = verify_doc(ref, ev.get("citation", ""), chunks)
            sup, sdetail = support_doc(ev.get("statement", ""), text) if prov in {"verified", "superseded"} else ("not_checked", "")
            ver.items.append(ItemVerdict(i, "document", prov, sup, f"{detail}; {sdetail}".strip("; ")))
    return ver
