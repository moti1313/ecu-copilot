"""Consistency check of the final assessments - runs after the model, next to provenance/support. No LLM.

Concept: design/CONCEPT.md §11 ("markieren, nicht verbieten"). The check never sets a cause, never changes an
assessment and never changes derive_finding(). It only makes certain unsupported or contradictory
commitments visible, so the engineer (and the benchmark) can see them.

Inputs are exclusively what the run stored: the report's `assessments` and the tool calls that were actually
executed (name, input, output). Nothing is recomputed from snapshots. If a check was not run in this run,
the flag says "not checked", not "contradictory".

Known limits of this first version (CONCEPT §11): assessments carry no link to their evidence, so flags are
reasoned hints, not conditions that evidence can clear; nested scopes ("station 2/B, all lots" contains a
single lot) are NOT treated as the same scope - K3 fires only on identical scope tuples; time windows are not
compared because assessments carry none.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

STATION_CAUSES = {"station_temperature", "cell_noise", "fixture", "sensor_t1"}
DEFECT_CLAIMS = {"suspected", "strong"}

TEXTS = {
    "K0": "Temperaturursache festgelegt, Sensorplausibilität (Iq↔T1) nicht geprüft",
    "K1": "Temperaturmessung dieses Messpfads in Zweifel; reale Übertemperatur nicht unabhängig belegt",
    "K2": "Gemeinsame Festlegung von Stationsursache und Bauteilverdacht benötigt getrennte Begründung",
    "K3": "Gemeinsame Festlegung benötigt getrennte Begründung; kann ein berechtigter Mehrfachfehler sein",
    "K4": "Stationsübergreifender Vergleich für dieses Los fehlt",
}
KINDS = {"K0": "coverage", "K1": "conflict", "K2": "hint", "K3": "hint", "K4": "coverage"}


@dataclass
class ConsistencyFlag:
    code: str  # K0..K4
    kind: str  # coverage | conflict | hint
    assessments: list[int]  # 0-based indices into report["assessments"]
    text: str
    detail: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------------------------
def _scope(a: dict) -> tuple[str | None, str | None, str | None]:
    s = a.get("scope") or {}
    norm = lambda v: None if v in (None, "", "null") else str(v).strip().upper()  # noqa: E731
    return norm(s.get("station")), norm(s.get("variant")), norm(s.get("lot"))


def _ok_outputs(tool_calls: list, name: str) -> list[tuple[dict, dict]]:
    """(input, output) of successful calls of one tool - JSON output without an 'error' key."""
    out = []
    for c in tool_calls or []:
        if getattr(c, "name", None) != name:
            continue
        try:
            o = json.loads(getattr(c, "output", "") or "")
        except (TypeError, ValueError):
            continue
        if not isinstance(o, dict) or "error" in o:
            continue
        out.append((getattr(c, "input", None) or {}, o))
    return out


def _covers(called: object, claimed: str | None) -> bool:
    """A call for 'all' (None) or for exactly the claimed station/variant covers the assessment."""
    return called in (None, "", "null") or (claimed is not None and str(called).strip().upper() == claimed)


def _describe_for(a: dict, tool_calls: list) -> list[dict]:
    st, var, _ = _scope(a)
    hits = []
    for inp, out in _ok_outputs(tool_calls, "describe_signal"):
        sc = out.get("scope") if isinstance(out.get("scope"), dict) else {}
        c_st, c_var = sc.get("station", inp.get("station")), sc.get("variant", inp.get("variant"))
        if st is not None and str(c_st).upper() != st:
            continue
        if not _covers(c_var, var):
            continue
        hits.append(out)
    return hits


# ---------------------------------------------------------------------------------------------
def check_consistency(report: dict | None, tool_calls: list) -> list[ConsistencyFlag]:
    flags: list[ConsistencyFlag] = []
    assessments = (report or {}).get("assessments") or []
    if not assessments:
        return flags

    for i, a in enumerate(assessments):
        validity = str(a.get("test_validity") or "")
        defect = str(a.get("defect_indication") or "")
        cause = str(a.get("root_cause") or "")
        st, var, lot = _scope(a)

        if validity == "invalid_temperature":
            described = _describe_for(a, tool_calls)
            if not described:
                flags.append(ConsistencyFlag("K0", KINDS["K0"], [i], TEXTS["K0"], "describe_signal wurde für diesen Geltungsbereich nicht erfolgreich ausgeführt"))
            else:
                decoupled = [d for d in described if str(d.get("iq_t1_relation") or "") == "decoupled"]
                same_scope_sensor = [
                    j for j, b in enumerate(assessments) if j != i and _scope(b) == (st, var, lot) and b.get("root_cause") == "sensor_t1"
                ]
                if decoupled or same_scope_sensor:
                    why = []
                    if decoupled:
                        why.append(f"describe_signal: iq_t1_relation=decoupled (Korrelation {decoupled[0].get('iq_t1_correlation')})")
                    if same_scope_sensor:
                        why.append(f"Bewertung {same_scope_sensor[0] + 1} nennt sensor_t1 für denselben Geltungsbereich")
                    flags.append(ConsistencyFlag("K1", KINDS["K1"], [i, *same_scope_sensor], TEXTS["K1"], "; ".join(why)))

        if cause in STATION_CAUSES and defect in DEFECT_CLAIMS:
            flags.append(ConsistencyFlag("K2", KINDS["K2"], [i], TEXTS["K2"], f"root_cause={cause} mit defect_indication={defect}"))

        if cause == "connector_lot" and defect in DEFECT_CLAIMS:
            cross = [
                (inp, out)
                for inp, out in _ok_outputs(tool_calls, "cluster_failures")
                if inp.get("station") in (None, "", "null")
                and str(out.get("by") or inp.get("by") or "") == "lot"
                and _covers(inp.get("variant"), var)
                and (lot is None or str((out.get("top") or {}).get("group") or "").upper() == lot)
            ]
            if not cross:
                flags.append(
                    ConsistencyFlag("K4", KINDS["K4"], [i], TEXTS["K4"], f"kein erfolgreicher cluster_failures-Aufruf ohne Stationsfilter für Los {lot or '?'} / Variante {var or 'alle'}")
                )

    # K3: identical scope tuple, one invalid_*, the other suspected/strong
    for i, a in enumerate(assessments):
        if not str(a.get("test_validity") or "").startswith("invalid"):
            continue
        for j, b in enumerate(assessments):
            if j == i or _scope(b) != _scope(a) or b.get("defect_indication") not in DEFECT_CLAIMS:
                continue
            flags.append(
                ConsistencyFlag(
                    "K3",
                    KINDS["K3"],
                    sorted([i, j]),
                    TEXTS["K3"],
                    f"Bewertung {i + 1}: {a.get('test_validity')}/{a.get('defect_indication')}/{a.get('root_cause')} · Bewertung {j + 1}: {b.get('test_validity')}/{b.get('defect_indication')}/{b.get('root_cause')}",
                )
            )
    # de-duplicate K3 pairs (i,j) and (j,i) can only arise if both are invalid and suspected - keep first
    seen, unique = set(), []
    for f in flags:
        key = (f.code, tuple(f.assessments))
        if key in seen:
            continue
        seen.add(key)
        unique.append(f)
    return unique


def summarize(flags: list[ConsistencyFlag]) -> dict:
    return {
        "count": len(flags),
        "flags": [f.as_dict() for f in flags],
        "method": "CONCEPT §11: K0/K4 Abdeckung, K1 Widerspruch, K2/K3 Prüfhinweis; nur gespeicherte Werkzeugaufrufe; Befund und Bewertungen unverändert",
    }
