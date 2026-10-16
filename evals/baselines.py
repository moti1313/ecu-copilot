"""Baselines for the benchmark (design/CONCEPT.md §5, ARCHITECTURE.md §4.3).

B0 - fair rule engine: the same deterministic tools as V2 (validity, change, clusters, descriptors),
     fixed decision rules, structured evidence refs by construction, no LLM. It knows the scope
     (station/variant) from the scenario, not from the question - it cannot read.
B1 - single-call RAG: one model call with the 10/60-minute stats and the top-5 document chunks pasted
     into the prompt, the V1 report schema, no tools. The "chatbot".

Both return an AskResult so the harness scores every system alike.
"""

from __future__ import annotations

import json
import time

from ecu_copilot import config
from ecu_copilot.copilot import tools
from ecu_copilot.copilot.agent import REPORT_SCHEMA_V1, SYSTEM_PROMPT_V1, AskResult, ToolCall, parse_report, summarize_tool_output
from ecu_copilot.copilot.metrics import Usage
from ecu_copilot.engineering.change import detect_change
from ecu_copilot.engineering.cluster import cluster_failures
from ecu_copilot.engineering.describe import describe_signal
from ecu_copilot.engineering.spec import load_spec
from ecu_copilot.engineering.validity import check_validity

# ------------------------------------------------------------------------------------------------
# B0
# ------------------------------------------------------------------------------------------------


def _call(result: AskResult, name: str, inputs: dict, fn, *args, **kwargs) -> dict:
    """Run an engineering function as a recorded tool call (so refs and the verifier work)."""
    t0 = time.perf_counter()
    out = fn(*args, **kwargs)
    out["scope"] = {"station": inputs.get("station"), "variant": inputs.get("variant"), "window_minutes": inputs.get("minutes")}
    text = json.dumps(out, ensure_ascii=False, default=str)
    result.tool_calls.append(
        ToolCall(
            name=name,
            input=inputs,
            output=text,
            result_preview=text[:300],
            summary=summarize_tool_output(name, text),
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
    )
    return out


def _ref(call_no: int, field: str, value, station=None, variant=None, minutes=None, doc_id=None, revision=None, section=None) -> dict:
    return {
        "tool_call": call_no,
        "field": field,
        "station": station,
        "variant": variant,
        "window_minutes": minutes,
        "value": value,
        "doc_id": doc_id,
        "revision": revision,
        "section": section,
    }


def run_b0(question: str, station: int | None, variant: str | None, minutes: int = 10) -> AskResult:
    """Rule engine. `station`/`variant` come from the scenario; for questions without a line scope it answers 'information'."""
    t0 = time.perf_counter()
    r = AskResult(provider="rules", model="B0", profile="b0")
    spec = load_spec()
    if station is None:
        r.report = parse_report(
            json.dumps(
                {
                    "answer_markdown": "B0 kann nur Linienzustände bewerten (keine Dokumentfrage).",
                    "assessments": [],
                    "hypotheses": [],
                    "evidence": [],
                    "next_test": None,
                    "affected_components": [],
                    "routing": [],
                }
            )
        )
        r.answer = r.report["answer_markdown"]
        r.latency_s = round(time.perf_counter() - t0, 2)
        return r

    twin = tools._get_twin()
    rows = twin.results(station=station, variant=variant, minutes=minutes, only_failed=False, limit=10000)
    rows60 = twin.results(station=station, variant=variant, minutes=60, only_failed=False, limit=10000)
    rows_lot = twin.results(station=None, variant=variant, minutes=30, only_failed=False, limit=10000)

    val = _call(r, "check_validity", {"station": station, "variant": variant, "minutes": minutes}, check_validity, rows, spec)  # call 1
    chg = _call(
        r,
        "detect_change",
        {"station": station, "variant": variant, "metric": "failure_rate", "minutes": 60, "bucket_s": 60},
        detect_change,
        rows60,
        metric="failure_rate",
        bucket_s=60,
    )  # 2
    lot = _call(
        r,
        "cluster_failures",
        {"station": None, "variant": variant, "by": "lot", "code": "E-120", "minutes": 30},
        cluster_failures,
        rows_lot,
        by="lot",
        code="E-120",
    )  # 3
    fw = _call(
        r,
        "cluster_failures",
        {"station": station, "variant": variant, "by": "firmware", "code": None, "minutes": 30},
        cluster_failures,
        rows60,
        by="firmware",
    )  # 4
    sig = _call(r, "describe_signal", {"station": station, "variant": variant, "minutes": 20}, describe_signal, rows, spec)  # 5

    assessments, evidence, hyps, comps, cause_names = [], [], [], [], []
    base_scope = {"station": station, "variant": variant, "lot": None}

    # rule 1a - TEST VALIDITY is decided per measurement by the specification (check_validity): a single
    #           INVALID E-204 / E-310 makes "invalid_temperature" / "invalid_noise" a finding - no minimum count.
    # rule 1b - the CAUSE claim (station temperature / cell noise) is a statement about the line and needs
    #           count, share and a signal: >= 3 such failures, >= 50 % of that code INVALID, and the descriptors
    #           flag the condition (T1 / noise outside the window). Otherwise root_cause stays "unknown".
    #           Review 16.10.: validity and cause were coupled through one threshold before - that would have
    #           handed the agent an advantage that only came from a restricted rule set.
    codes = val["codes"]
    dominant = max(codes, key=lambda c: codes[c]["fail_verdicts"]) if codes else None
    env_code = next((c for c in ("E-204", "E-310") if c in codes and codes[c]["invalid_per_spec"] >= 1), None)
    if env_code == "E-204" and sig["iq_t1_relation"] == "decoupled":
        env_code = None  # the reported temperature is not trustworthy - rule 3 (sensor) handles this group
    if env_code:
        inval_share = round(100.0 * codes[env_code]["invalid_per_spec"] / codes[env_code]["fail_verdicts"], 1)
        validity = "invalid_temperature" if env_code == "E-204" else "invalid_noise"
        flag_key = "T1 outside" if env_code == "E-204" else "ambient noise above"
        signal = any(flag_key in f for f in sig.get("flags", []))
        cause_claim = codes[env_code]["fail_verdicts"] >= 3 and inval_share >= 50 and signal
        cause = ("station_temperature" if env_code == "E-204" else "cell_noise") if cause_claim else "unknown"
        assessments.append({"scope": base_scope, "test_validity": validity, "defect_indication": "none_assessable", "root_cause": cause})
        comps += ["T1", "U1"] if env_code == "E-204" else ["MIC"]
        cause_names.append(cause)
        evidence.append(
            {
                "statement": f"{codes[env_code]['invalid_per_spec']} von {codes[env_code]['fail_verdicts']} {env_code}-Fails sind nach Spezifikation INVALID ({'T1 außerhalb 18–32 °C' if env_code == 'E-204' else 'Lärm > 45 dB(A)'})",
                "source_type": "live",
                "ref": _ref(1, f"codes.{env_code}.invalid_per_spec", codes[env_code]["invalid_per_spec"], station, variant, minutes),
                "citation": f"EOL-{station} / {variant or 'A+B'} / {minutes} min",
                "supports": "H1 Prüfumgebung",
            }
        )
        rule = val["rules"]["board_temp_c" if env_code == "E-204" else "ambient_noise_db"]["rule"]
        doc_id, sec = rule.split(" §")
        evidence.append(
            {
                "statement": "Messungen außerhalb des Gültigkeitsfensters sind INVALID, nicht FAIL; Wiederholung unter gültigen Bedingungen",
                "source_type": "document",
                "ref": _ref(None, None, None, doc_id=doc_id, revision=spec["revision"], section=sec),
                "citation": rule,
                "supports": "H1 Prüfumgebung",
            }
        )
        hyps.append(
            {
                "title": "H1 Prüfumgebung",
                "support": "strong",
                "rationale": f"{inval_share} % der {env_code}-FAIL-Verdicte sind nach Spezifikation ungültig.",
                "test": {
                    "title": "Wiederholungsprüfung unter gültigen Bedingungen",
                    "discriminates": ["H1 Prüfumgebung", "H2 Bauteil"],
                    "prediction_if_true": "Einheiten bestehen",
                    "prediction_if_false": "Einheiten fallen erneut durch",
                },
            }
        )

    # rule 2: lot concentration of E-120 (real failure)
    if lot["concentrated"]:
        top = lot["top"]
        assessments.append(
            {
                "scope": {"station": None, "variant": variant, "lot": top["group"]},
                "test_validity": "valid",
                "defect_indication": "strong",
                "root_cause": "connector_lot",
            }
        )
        comps.append("J3")
        cause_names.append("connector_lot")
        evidence.append(
            {
                "statement": f"E-120 konzentriert auf Los {top['group']}: Rate {top['failure_rate_pct']} % vs. {top['failure_rate_others_pct']} % sonst (Rate-Verhältnis {top['rate_ratio']}, z={top['z']})",
                "source_type": "live",
                "ref": _ref(3, "top.rate_ratio", top["rate_ratio"], None, variant, 30),
                "citation": f"alle Stationen / {variant or 'A+B'} / 30 min",
                "supports": "H2 Steckverbinder-Los",
            }
        )
        evidence.append(
            {
                "statement": "E-120 ist praktisch nie umgebungsbedingt; losabhängige Häufung deutet auf Steckverbinder J3 (Pins 5/6)",
                "source_type": "document",
                "ref": _ref(None, None, None, doc_id="FMEA-DCU-B2", revision="7", section="3"),
                "citation": "FMEA-DCU-B2 §3",
                "supports": "H2 Steckverbinder-Los",
            }
        )
        hyps.append(
            {
                "title": "H2 Steckverbinder-Los",
                "support": "strong",
                "rationale": "Loskonzentration mit Bezugsgröße (Rate-Verhältnis) und z-Score.",
                "test": {
                    "title": "Los trennen, Stichprobe J3 röntgen/schliffen",
                    "discriminates": ["H2 Steckverbinder-Los"],
                    "prediction_if_true": "Defekt an J3 in den Losteilen",
                    "prediction_if_false": "kein Befund an J3",
                },
            }
        )

    # rule 3: sensor decoupling
    if sig["iq_t1_relation"] == "decoupled":
        assessments.append({"scope": base_scope, "test_validity": "unknown", "defect_indication": "none", "root_cause": "sensor_t1"})
        comps.append("T1")
        cause_names.append("sensor_t1")
        evidence.append(
            {
                "statement": "T1 und Ruhestrom sind entkoppelt: " + (sig["flags"][-1] if sig["flags"] else ""),
                "source_type": "live",
                "ref": _ref(5, "iq_t1_relation", "decoupled", station, variant, 20),
                "citation": f"EOL-{station} / {variant or 'A+B'} / 20 min",
                "supports": "H3 T1-Sensor",
            }
        )
        # the same evidence duty as the agent: the leakage model and the validity rule come from documents
        evidence.append(
            {
                "statement": "Sleep current rises ~3.5 % per kelvin above 25 °C - a reported temperature rise without a current rise contradicts the leakage model",
                "source_type": "document",
                "ref": _ref(None, None, None, doc_id="DS-MCU-XM32F7", revision="2.1", section="7.3"),
                "citation": "DS-MCU-XM32F7 §7.3",
                "supports": "H3 T1-Sensor",
            }
        )
        evidence.append(
            {
                "statement": "The validity window refers to the station sensor T1; if T1 is wrong, validity of the results cannot be decided from it",
                "source_type": "document",
                "ref": _ref(None, None, None, doc_id="TS-DCU-EOL", revision=spec["revision"], section="4.2"),
                "citation": "TS-DCU-EOL §4.2",
                "supports": "H3 T1-Sensor",
            }
        )
        hyps.append(
            {
                "title": "H3 T1-Sensor",
                "support": "moderate",
                "rationale": "Temperaturanzeige ohne physikalische Wirkung auf den Ruhestrom.",
                "test": {
                    "title": "T1 gegen Referenzthermometer prüfen",
                    "discriminates": ["H3 T1-Sensor", "H1 Prüfumgebung"],
                    "prediction_if_true": "Abweichung > 2 K",
                    "prediction_if_false": "Sensor stimmt",
                },
            }
        )

    # rule 4: firmware concentration
    if fw["concentrated"] and fw["top"]["group"] != "n/a":
        assessments.append({"scope": base_scope, "test_validity": "valid", "defect_indication": "suspected", "root_cause": "firmware"})
        comps.append("SERVICE_IF")
        cause_names.append("firmware")
        evidence.append(
            {
                "statement": f"Fehler konzentriert auf Firmware {fw['top']['group']} (Rate-Verhältnis {fw['top']['rate_ratio']})",
                "source_type": "live",
                "ref": _ref(4, "top.rate_ratio", fw["top"]["rate_ratio"], station, variant, 30),
                "citation": f"EOL-{station} / {variant or 'A+B'} / 60 min",
                "supports": "H4 Firmware",
            }
        )
        hyps.append({"title": "H4 Firmware", "support": "moderate", "rationale": "Versionsbezug.", "test": None})

    # rule 5: fixture - E-205 on this station across variants
    if codes.get("E-205", {}).get("fail_verdicts", 0) >= 5 and dominant == "E-205":
        assessments.append(
            {"scope": base_scope, "test_validity": "invalid_fixture", "defect_indication": "none_assessable", "root_cause": "fixture"}
        )
        comps.append("FIXTURE")
        cause_names.append("fixture")

    if not assessments:
        if chg.get("significant"):
            assessments.append({"scope": base_scope, "test_validity": "valid", "defect_indication": "suspected", "root_cause": "unknown"})
        else:
            assessments.append({"scope": base_scope, "test_validity": "valid", "defect_indication": "none", "root_cause": "none"})
    if chg.get("significant"):
        evidence.insert(
            0,
            {
                "statement": f"Ausfallrate {chg['level_before']} % → {chg['level_after']} % ab {chg['onset'][11:16]} (z={chg['z']})",
                "source_type": "live",
                "ref": _ref(2, "level_after", chg["level_after"], station, variant, 60),
                "citation": f"EOL-{station} / {variant or 'A+B'} / 60 min",
                "supports": "",
            },
        )

    next_test = None
    if "station_temperature" in cause_names or "cell_noise" in cause_names:
        next_test = {
            "title": "Wiederholungsprüfung der INVALID-Einheiten nach Korrektur der Stationsbedingung",
            "expectation": "Einheiten bestehen, falls kein zusätzlicher Defekt",
            "duration": "≈ 15 min",
            "units": [e["serial"] for e in val["invalid_examples"][:10]],
            "block_units": False,
        }
    if "connector_lot" in cause_names:
        next_test = {
            "title": ("Los " + lot["top"]["group"] + " trennen und sperren; ")
            + (next_test["title"] if next_test else "Stichprobe J3 prüfen"),
            "expectation": "Losteile fallen weiterhin durch",
            "duration": "≈ 30 min",
            "units": [],
            "block_units": True,
        }

    report = {
        "answer_markdown": "Befund (Regelwerk B0)\n- "
        + "\n- ".join(f"{a['scope']}: {a['test_validity']}, {a['defect_indication']}, Ursache {a['root_cause']}" for a in assessments)
        + "\n\nBelege\n- "
        + "\n- ".join(e["statement"] + f" ({e['citation']})" for e in evidence)
        + ("\n\nEmpfehlung\n- " + next_test["title"] if next_test else ""),
        "assessments": assessments,
        "hypotheses": hyps,
        "evidence": evidence,
        "next_test": next_test,
        "affected_components": sorted(set(comps)),
        "routing": ["live", "docs"],
    }
    r.report = parse_report(json.dumps(report, ensure_ascii=False))
    r.answer = r.report["answer_markdown"]
    r.iterations = 0
    r.latency_s = round(time.perf_counter() - t0, 2)
    return r


# ------------------------------------------------------------------------------------------------
# B1
# ------------------------------------------------------------------------------------------------
B1_SYSTEM = (
    SYSTEM_PROMPT_V1.split("How to work")[0]
    + """You have NO tools. The current statistics and the most relevant documentation sections are pasted below the question. Answer only from that material, cite document sections, and output the JSON report described here:
"""
    + SYSTEM_PROMPT_V1.split("Output format")[1]
)


def run_b1(question: str, model: str | None = None) -> AskResult:
    t0 = time.perf_counter()
    model = model or config.AGENT_MODEL
    r = AskResult(provider=config.LLM_PROVIDER, model=model, profile="b1")
    usage = Usage()
    twin = tools._get_twin()
    try:
        stats10, stats60 = twin.stats(minutes=10), twin.stats(minutes=60)
        hits = tools._get_index().search(question, k=5)
    except Exception as e:  # noqa: BLE001
        r.error = f"context gathering failed: {e}"
        r.latency_s = round(time.perf_counter() - t0, 2)
        return r
    for name, out in (("get_station_stats", stats10), ("get_station_stats", stats60), ("search_docs", hits)):
        text = json.dumps(out, ensure_ascii=False, default=str)
        r.tool_calls.append(
            ToolCall(name=name, input={"pasted": True}, output=text, result_preview=text[:300], summary=summarize_tool_output(name, text))
        )
    context = (
        f"\n\n--- Live statistics, last 10 minutes ---\n{json.dumps(stats10, default=str)}\n\n--- Live statistics, last 60 minutes ---\n{json.dumps(stats60, default=str)}"
        + "\n\n--- Documentation sections ---\n"
        + "\n\n".join(f"[{h['citation']}]\n{h['text']}" for h in hits)
    )
    try:
        if config.LLM_PROVIDER == "openai":
            import openai

            params = {
                "model": model,
                "messages": [{"role": "system", "content": B1_SYSTEM}, {"role": "user", "content": question + context}],
                "max_completion_tokens": config.AGENT_MAX_TOKENS,
                "response_format": {"type": "json_schema", "json_schema": {"name": "report", "strict": True, "schema": REPORT_SCHEMA_V1}},
            }
            if model.startswith(("gpt-5", "o")):
                params["reasoning_effort"] = config.AGENT_EFFORT
            resp = openai.OpenAI().chat.completions.create(**params)
            u = resp.usage
            cached = getattr(getattr(u, "prompt_tokens_details", None), "cached_tokens", 0) or 0
            usage.input_tokens += (u.prompt_tokens or 0) - cached
            usage.cache_read_input_tokens += cached
            usage.output_tokens += u.completion_tokens or 0
            r.answer = resp.choices[0].message.content or ""
            r.stop_reason = resp.choices[0].finish_reason
            if r.stop_reason == "length":
                r.error = "answer truncated (max_completion_tokens)"
        else:
            import anthropic

            resp = anthropic.Anthropic().messages.create(
                model=model,
                max_tokens=config.AGENT_MAX_TOKENS,
                system=B1_SYSTEM,
                messages=[{"role": "user", "content": question + context}],
                output_config={"effort": config.AGENT_EFFORT, "format": {"type": "json_schema", "schema": REPORT_SCHEMA_V1}},
            )
            usage.add(resp.usage)
            r.answer = "".join(b.text for b in resp.content if b.type == "text")
            r.stop_reason = resp.stop_reason
        r.iterations = 1
    except Exception as e:  # noqa: BLE001
        r.error = f"{type(e).__name__}: {str(e)[:300]}"
    r.report = parse_report(r.answer)
    if r.report:
        r.answer = r.report["answer_markdown"]
    r.usage = {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cache_read_input_tokens": usage.cache_read_input_tokens,
        "cache_creation_input_tokens": 0,
    }
    r.cost_usd = round(usage.cost_usd(model), 5)
    r.latency_s = round(time.perf_counter() - t0, 2)
    return r
