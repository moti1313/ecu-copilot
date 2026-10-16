"""Evidence verification: provenance against this run's tool outputs and the document index; support heuristics."""

import json

from ecu_copilot.copilot.agent import ToolCall, derive_finding, parse_report
from ecu_copilot.copilot.verify import parse_citation, resolve_path, verify_report
from ecu_copilot.engineering.spec import load_spec

STATS = {
    "window_minutes": 10,
    "groups": [
        {"station": 1, "variant": "A", "failure_rate_pct": 2.1, "mean_board_temp_c": 24.9},
        {"station": 2, "variant": "B", "failure_rate_pct": 13.4, "mean_board_temp_c": 34.6},
    ],
}
VALIDITY = {
    "scope": {"station": 2, "variant": "B", "window_minutes": 10},
    "codes": {"E-204": {"fail_verdicts": 28, "invalid_per_spec": 28}},
}


def _calls():
    return [
        ToolCall(name="get_station_stats", input={"minutes": 10}, output=json.dumps(STATS)),
        ToolCall(name="check_validity", input={"station": 2, "variant": "B", "minutes": 10}, output=json.dumps(VALIDITY)),
    ]


def _ev(statement, source_type, ref, citation="", supports=""):
    base = {
        "tool_call": None,
        "field": None,
        "station": None,
        "variant": None,
        "window_minutes": None,
        "value": None,
        "doc_id": None,
        "revision": None,
        "section": None,
    }
    return {"statement": statement, "source_type": source_type, "ref": {**base, **ref}, "citation": citation, "supports": supports}


def test_resolve_path_selectors():
    assert resolve_path(STATS, "groups[station=2,variant=B].failure_rate_pct") == 13.4
    assert resolve_path(VALIDITY, "codes.E-204.invalid_per_spec") == 28
    assert resolve_path(STATS, "groups[0].station") == 1


def test_live_provenance_verified_wrong_scope_and_mismatch(bm25_index):
    report = {
        "evidence": [
            _ev(
                "Station 2/B: 13.4 % Ausfall",
                "live",
                {
                    "tool_call": 1,
                    "field": "groups[station=2,variant=B].failure_rate_pct",
                    "station": 2,
                    "variant": "B",
                    "window_minutes": 10,
                    "value": 13.4,
                },
            ),
            _ev(
                "Station 2/B: 24.9 °C",
                "live",
                {
                    "tool_call": 1,
                    "field": "groups[station=1,variant=A].mean_board_temp_c",
                    "station": 2,
                    "variant": "B",
                    "window_minutes": 10,
                    "value": 24.9,
                },
            ),
            _ev(
                "28 INVALID",
                "live",
                {"tool_call": 2, "field": "codes.E-204.invalid_per_spec", "station": 2, "variant": "B", "window_minutes": 10, "value": 30},
            ),
            _ev("ohne Ref", "live", {}),
            _ev(
                "Station 1 Wert für Station 2 ausgegeben",
                "live",
                {"tool_call": 2, "field": "codes.E-204.invalid_per_spec", "station": 1, "variant": "A", "window_minutes": 10, "value": 28},
            ),
        ]
    }
    v = verify_report(report, _calls(), bm25_index._chunks, load_spec())
    assert [i.provenance for i in v.items] == ["verified", "wrong_scope", "value_mismatch", "no_ref", "wrong_scope"]
    # item 2 resolves (the path selects station 1) - but the ref claims station 2; the path check passes, the claim
    # is caught only if the statement/ref scope is checked against the selected group: document the limitation.
    assert v.summary()["provenance"]["live"] == {"ok": 1, "total": 5}


def test_doc_provenance_and_support(bm25_index):
    report = {
        "evidence": [
            _ev(
                "Measurements valid only between 18 °C and 32 °C; outside INVALID",
                "document",
                {"doc_id": "TS-DCU-EOL", "revision": "D", "section": "4.2"},
                "TS-DCU-EOL §4.2",
            ),
            _ev("Limit 450 µA", "document", {}, "TS-DCU-EOL §9.9"),
            _ev("x", "document", {}, "NO-SUCH-DOC §1"),
            _ev(
                "Background noise must be below 45 dB(A) during the motor run",
                "document",
                {"doc_id": "TS-DCU-EOL", "revision": "C", "section": "6.1"},
                "",
            ),
        ]
    }
    v = verify_report(report, [], bm25_index._chunks, load_spec())
    assert [i.provenance for i in v.items] == ["verified", "unknown_section", "not_found", "superseded"]
    assert v.items[0].support == "supported"
    assert v.summary()["provenance"]["docs"] == {"ok": 1, "total": 4}


def test_live_support_against_spec(bm25_index):
    report = {
        "evidence": [
            _ev(
                "Iq 481 µA über dem Limit",
                "live",
                {
                    "tool_call": 1,
                    "field": "groups[station=2,variant=B].failure_rate_pct",
                    "station": 2,
                    "variant": "B",
                    "window_minutes": 10,
                    "value": 13.4,
                },
            ),
        ]
    }
    calls = [ToolCall(name="get_station_stats", input={"minutes": 10}, output=json.dumps(STATS))]
    v = verify_report(report, calls, bm25_index._chunks, load_spec())
    assert v.items[0].support == "not_checked"  # failure_rate_pct is not a limit comparison we check


def test_parse_citation_forms():
    assert parse_citation("TS-DCU-EOL §4.2") == ("TS-DCU-EOL", None, "4.2")
    assert parse_citation("FMEA-DCU-B2 item 7") == ("FMEA-DCU-B2", None, "7")
    assert parse_citation("TS-DCU-EOL Rev. D §5") == ("TS-DCU-EOL", "D", "5")


def test_v2_report_parsing_and_derived_finding():
    rep = parse_report(
        json.dumps(
            {
                "answer_markdown": "a",
                "assessments": [
                    {
                        "scope": {"station": 2, "variant": "B", "lot": None},
                        "test_validity": "invalid_temperature",
                        "defect_indication": "none_assessable",
                        "root_cause": "station_temperature",
                    },
                    {
                        "scope": {"station": None, "variant": "B", "lot": "L2439-07"},
                        "test_validity": "valid",
                        "defect_indication": "strong",
                        "root_cause": "connector_lot",
                    },
                ],
                "hypotheses": [],
                "evidence": [],
                "next_test": None,
                "affected_components": [],
                "routing": ["live"],
            }
        )
    )
    assert rep["finding"] == "mixed"
    assert derive_finding({"assessments": []}) == "information"
    assert derive_finding({"assessments": [{"test_validity": "valid", "defect_indication": "none", "root_cause": "none"}]}) == "unclear"
    assert parse_report(json.dumps({"answer_markdown": "a", "finding": "pseudo_failure"}))["finding"] == "pseudo_failure"


def test_doc_citation_normalisation(bm25_index):
    report = {
        "evidence": [
            _ev("valid 18 to 32 °C", "document", {"doc_id": "TS-DCU-EOL", "revision": "Rev. D", "section": "§4.2"}, "TS-DCU-EOL §4.2"),
            _ev(
                "lot dependent E-120 cluster connector J3",
                "document",
                {"doc_id": "FMEA-DCU-B2", "revision": None, "section": "section 3"},
                "",
            ),
        ]
    }
    v = verify_report(report, [], bm25_index._chunks, load_spec())
    assert [i.provenance for i in v.items] == ["verified", "verified"]
