# Architektur V2 – ECU Copilot

Status: Entwurf zur Abstimmung (16.10.2026). Ergänzt `CONCEPT.md`; Begründungen in `RESEARCH.md`, Ist-Zustand in `AUDIT.md`.

**Einordnung vom 17.10.2026:** Dieses Dokument bleibt der V2-**Zielentwurf** und enthält auch noch nicht umgesetzte Funktionen. Für den am Code abgeglichenen Ist-Stand mit Systemkontext, Datenfluss und Sequenzdiagramm siehe [ARCHITECTURE_CURRENT.md](ARCHITECTURE_CURRENT.md). Präsentationsfolien und Sprechtext: [presentation/README.md](presentation/README.md).

## 1. Schichten

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 5  Oberfläche · Untersuchungs-Arbeitsplatz (A) · Leitstand (B) · Akte (C)│
├─────────────────────────────────────────────────────────────────────────┤
│ 4  Mensch in der Schleife · Belege prüfen/ablehnen · Test freigeben ·    │
│    Ergebnis erfassen · Protokoll mit Trace-ID                            │
├─────────────────────────────────────────────────────────────────────────┤
│ 3  Agent (ein Agent) · Tool-Aufrufe · Hypothesen · Testplanung ·         │
│    strukturierter Report  →  Belegprüfung (Verifikationsmodul)           │
├─────────────────────────────────────────────────────────────────────────┤
│ 2  Deterministische Ingenieurschicht (Python, keine KI)                  │
│    check_validity · detect_change · cluster_failures · describe_signal · │
│    simulate_retest · Spezifikation (maschinenlesbar, versioniert)        │
├─────────────────────────────────────────────────────────────────────────┤
│ 1  Daten · Twin (Messungen, Ereignisse, Störungen, Firmware-Version) ·   │
│    Dokumente (Markdown, Revisionen) · Stückliste · Szenario-Bank         │
├─────────────────────────────────────────────────────────────────────────┤
│ 0  Querschnitt · Evals (Benchmark, Baselines) · Observability (OTel,     │
│    Kosten, Latenz) · Tests · Container                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

**Regel:** Schicht 3 darf nur über Schicht 2 auf Schicht 1 zugreifen. Rohdaten (Einzelergebnisse) erreichen das Modell nur in kompakter, von Schicht 2 vorverarbeiteter Form.

## 2. Schicht 1 – Daten

### 2.1 Twin (bestehend, erweitert)
- Neue Felder je Ergebnis: `firmware_version` (Station), `t1_offset_c` wirkt auf die *gemeldete* Temperatur (Sensorfehler), nicht auf die physikalische.
- Neue Störungstypen: `sensor_offset` (station, offset_c), `firmware_change` (station, version, flash_time_factor), `fixture_fault` (station, operating_current_bias_a).
- Neue Endpunkte: `POST /retest` (Einheiten unter aktuellem Stationszustand erneut prüfen, Ergebnisse markiert `retest_of`), `POST /simulate` (siehe 3.4).

### 2.2 Spezifikation maschinenlesbar – `docs/spec/TS-DCU-EOL.json`
```json
{"doc_id":"TS-DCU-EOL","revision":"D","effective":"2026-05-12","status":"current",
 "limits":{"A":{"quiescent_max_ua":350,"flash_max_s":45},"B":{"quiescent_max_ua":450,"flash_max_s":60},
           "operating_current_a":[1.0,2.4],"acoustic_min_score":70},
 "validity":{"board_temp_c":[18,32],"ambient_noise_db_max":45},
 "codes":{"E-120":{"meaning":"No LIN communication","first_check":"J3, solder 5/6, lot history","environmental":false},
          "E-204":{"meaning":"Quiescent current above limit","first_check":"T1 (4.2), then unit","environmental":true}, "...":{}},
 "escalation":{"rate_10min_pct":5,"rate_shift_pct":3}}
```
Quelle der Wahrheit bleibt das Markdown (für RAG und Zitate); die JSON wird daraus **generiert und im Test gegen das Markdown geprüft** (Konsistenztest). Eine zweite Datei `TS-DCU-EOL.rev-C.json` (status: superseded, 400 µA) für Szenario S10.

### 2.3 Dokumente mit Revision
Chunk-Metadaten erhalten `revision`, `status` (current/superseded), `effective`. Suche filtert standardmäßig `status=current`; superseded nur auf Anfrage (`include_superseded=true`). Zitat-Format: `TS-DCU-EOL Rev. D §4.2`.

### 2.4 Szenario-Bank – `evals/scenarios/*.json`
```json
{"id":"S05-sensor-offset","question":"…","setup":[{"type":"sensor_offset","station":2,"offset_c":8}],"settle_s":150,
 "truth":{"finding":"unclear","root_cause":"t1_sensor","components":["T1"],"next_test_keywords":["Sensor","Referenz"],
          "required_tools":["check_validity","describe_signal"],"must_cite":["TS-DCU-EOL §4.2"]},
 "solvability":{"metric":"iq_vs_t1_decoupling","min_effect":0.5}}
```

## 3. Schicht 2 – Deterministische Ingenieurschicht

Alle Funktionen sind reine Python-Funktionen auf Twin-Daten + Spezifikation, **unit-getestet**, und werden dem Agenten als Tools angeboten. Sie ersetzen `get_station_stats`/`get_recent_results` nicht, sondern sitzen davor.

| Tool | Eingabe | Ausgabe (kompakt) | Herkunft der Idee |
|---|---|---|---|
| `check_validity(station, variant, minutes)` | Fenster | je Fehlercode: Anzahl FAIL, davon **INVALID nach Spezifikation** (T1 außerhalb, Lärm über Limit) mit Regel-Referenz; Liste der betroffenen Serials (max. 20) | Spezifikation §4.2/§6.1; KG-HiL: Evidenz zuerst |
| `detect_change(station, variant, metric, minutes)` | Metrik (failure_rate, quiescent, temp, noise) | Onset-Zeitpunkt, Niveau vorher/nachher, Effektgröße (z), „signifikant: ja/nein" – CUSUM oder Zwei-Fenster-Test | CausalPulse Anomalieerkennung; Agent-Pitfall „falsches Zeitfenster" |
| `cluster_failures(station, variant, minutes, by)` | by = lot \| code \| firmware \| hour | Verteilung + Konzentrationsmaß (z. B. Anteil des größten Clusters, Erwartung bei Gleichverteilung) | FMEA Item 7; Pitfall „Symptom als Ursache" |
| `describe_signal(station, variant, minutes)` | Fenster | Text-Deskriptoren: Mittel/Min/Max/Trend je Messgröße, **Korrelation Iq↔T1**, Flags („T1 außerhalb seit 21:38", „Iq folgt T1 nicht") | Sensor-Level-Paper: Deskriptoren statt Rohdaten |
| `simulate_retest(serials, conditions)` | Serials + Zielbedingungen (z. B. board_temp_c=25) | vorhergesagtes Ergebnis je Einheit aus dem **Modell** (Leckstromkennlinie, typische Streuung), klar markiert `simulation: true`, mit Annahmen | Prozessanlagen-Paper: Twin-Validierung vor Maßnahme |

**Simulation vs. Wiederholungsprüfung – bewusst zwei Pfade, damit sie sich nicht gegenseitig bestätigen:**
- `simulate_retest` rechnet mit der *Modellannahme* (Kennlinie, Streuung) und kennt **keine** Einheit-Zustände.
- `POST /retest` misst im Twin dieselben **Einheiten mit ihrem persistenten Zustand** erneut: Der Twin führt je Serial einen latenten Zustand (z. B. `lin_defect: true` für Einheiten aus dem schlechten Los, individueller Ruhestrom-Offset) und misst unter den *aktuellen* Stationsbedingungen. Ein defektes Gerät fällt also auch nach Abkühlung durch; ein neu gewürfeltes Gerät wäre kein Re-Test.
- Beide bleiben Ergebnisse eines Modells (der Twin ist einer). Das UI sagt es: „Simulation (Modell)" vs. „Wiederholungsprüfung (Twin-Messung)". Was „Bestätigung" im echten Werk bedeutet, steht in den Production Notes.
| `search_docs`, `lookup_part`, `draft_8d_report` | wie V1 | + Revision in Zitaten | – |

`get_station_stats` bleibt; `get_recent_results` wird auf max. 40 Ergebnisse begrenzt und liefert die Zusammenfassung zuerst.

## 4. Schicht 3 – Agent und Verifikation

### 4.1 Agent
Unverändert ein Agent (Anthropic Tool Runner / OpenAI-Loop). Report-Schema V2 (ersetzt das einzelne `finding`, das Mehrfachfehler nicht ausdrücken konnte):

```json
{
 "answer_markdown": "…",
 "assessments": [                                  // eine Bewertung je betroffener Gruppe
   {"scope": {"station": 2, "variant": "B", "lot": null},
    "test_validity": "invalid_temperature",        // valid | invalid_temperature | invalid_noise | invalid_fixture | unknown
    "defect_indication": "none_assessable",        // none_assessable (Prüfung ungültig) | none | suspected | strong
    "root_cause": "station_temperature"}           // kontrolliertes Vokabular: station_temperature, cell_noise, fixture,
 ],                                                //   sensor_t1, firmware, connector_lot, component_u1/u7/u12, unknown, none
 "hypotheses": [{"title": "…", "support": "strong|moderate|weak|rejected", "rationale": "…",
                 "test": {"title": "…", "discriminates": ["H1","H2"], "prediction_if_true": "…", "prediction_if_false": "…"}}],
 "evidence": [
   {"statement": "…", "source_type": "live",
    "ref": {"tool_call": 3, "field": "groups[station=2,variant=B].failure_rate_pct", "window_minutes": 10, "value": 13.4},
    "supports": "H1"},
   {"statement": "…", "source_type": "document",
    "ref": {"doc_id": "TS-DCU-EOL", "revision": "D", "section": "4.2"}, "supports": "H1"}
 ],
 "next_test": {"title": "…", "expectation": "…", "duration": "…", "units": ["DCUB-…"], "block_units": false} | null,
 "affected_components": ["T1","U1"],
 "routing": ["live","docs"]
}
```
Regeln: **„Prüfung ungültig" ist keine Aussage über das Bauteil** – `defect_indication: none_assessable` heißt „nicht bewertbar, Wiederholung unter gültigen Bedingungen", nie „in Ordnung". Gleichzeitige Befunde (S08) sind zwei `assessments` (z. B. `invalid_temperature` für Station 2/B und `valid` + `strong` + `connector_lot` für Los L2439-07). Ein Test muss sagen, welche Hypothesen er trennt (CoffeeBench).

Prompt-Regeln neu: „Benutze `check_validity`, bevor du über Gültigkeit sprichst. Benutze `detect_change`, bevor du ‚seit X Minuten' sagst. Jeder Live-Beleg nennt Werkzeugaufruf, Feld, Station, Variante und Fenster. Rechne nicht selbst."

### 4.2 Verifikationsmodul (`copilot/verify.py`)
Läuft nach dem Modell, vor der Antwort. Kein LLM. Zwei getrennte Prüfungen mit getrennten Namen – **Herkunft** und **Stützung**:

| Prüfung | Live-Beleg | Dokument-Beleg |
|---|---|---|
| **Herkunft verifiziert** (`provenance`) | `ref` zeigt auf einen Werkzeugaufruf dieses Laufs; das Feld existiert in dessen Ausgabe **für genau Station/Variante/Fenster**; der Wert stimmt (Toleranz 1 % / Rundung). 32 °C an Station 1 belegt nichts über Station 2. | `doc_id`/`revision`/`section` existieren im Index; Revision ist `current` (sonst `superseded`). |
| **Stützung geprüft** (`support`) | Die Behauptung passt zur Richtung des Werts (z. B. „über Limit" ⇔ Wert > Limit aus Spezifikation) – nur für die Typen, die wir deterministisch prüfen können; sonst `not_checked`. | Der zitierte Abschnitt enthält die Schlüsselbegriffe der Behauptung (Zahlen, Codes, Fachwörter) oder hat hohe Ähnlichkeit; Ergebnis `supported` / `weak` / `not_checked`. Das ist eine Heuristik und wird so benannt. |

Report-Ebene: `verification: {provenance: {live: n/m, docs: n/m}, support: {live: n/m, docs: n/m}, flags: [...]}`. Im UI je Beleg zwei Marken (Herkunft ✓/✗, Stützung ✓/~/–). Ein Beleg ohne verifizierte Herkunft wird rot und zählt im Benchmark als fehlerhaft. Metriken: Herkunfts-Rate, Stützungs-Rate, Zitat-Validität.

### 4.3 Baselines (`evals/baselines.py`)
- **B0 – faires Regelwerk:** darf **alle** Werkzeuge der Schicht 2 nutzen, dieselben wie V2. Entscheidungsregeln je Gruppe: `check_validity` → INVALID-Anteil > 50 % ⇒ `test_validity` entsprechend; `describe_signal` → „Iq folgt T1 nicht" ⇒ `sensor_t1`; `cluster_failures(by=firmware)` → Fehler nur in einer Firmware-Version ⇒ `firmware`; `cluster_failures(by=lot)` → **Lift** (Fehleranteil des Loses ÷ Prüfanteil des Loses) > 2 und n ≥ 10 ⇒ `connector_lot`; E-205 über alle Varianten einer Station ⇒ `fixture`; sonst `unknown`. Kein LLM. Der Lift ist Pflicht – 70 % der Fehler aus einem Los sagen nichts, wenn das Los 90 % der Teile stellt.
- **B1:** ein Aufruf: Statistik 10/60 min + Top-5-Chunks + Frage → Report-Schema. Keine Tools.
- **B2 (optional, bei Zugang):** TypeSafe-AI **Jev** (System-One-Modell, typisierte Entscheidungen mit kalibrierter Wahrscheinlichkeit): Zustand = Deskriptoren aus `describe_signal` + `check_validity`, Frage = *Choice* {pseudo_failure, real_failure, unclear}. Misst, ob ein Klassifikator mit Wahrscheinlichkeit für die Triage reicht – und ob seine Kalibrierung auf unseren Szenarien stimmt.

### 4.4 Router und Triage (optional, Ergänzung – kein Ersatz des Agenten)
Zwei Aufgaben vor dem Agenten, hinter einem Schalter `ROUTER=none|llm|jev`:
- **Router:** *Choice* „braucht die Frage live / docs / beides / außerhalb" (Idee: Lagerdiagnose-Paper, Router-Genauigkeit 0,98). Mit `jev`: ~0,2 s, ~0,0001 $; mit `llm`: ein kleiner Modellaufruf; mit `none`: der Agent entscheidet implizit wie in V1. Off-Topic endet vor dem teuren Modell. Die Routing-Entscheidung wird geloggt und im Benchmark bewertet (Explorations-Vollständigkeit).
- **Triage (System One vor System Two):** bei jeder Ratenänderung (`detect_change` signifikant) eine *Choice*-Klassifikation mit Wahrscheinlichkeit; Schwellen entscheiden, ob der Leitstand nur markiert, den Agenten startet oder den Ingenieur ruft. Jev liefert hier, was ein LLM nicht liefern kann: eine trainierte, nicht erfundene Wahrscheinlichkeit – **ihre Kalibrierung ist eine Benchmark-Frage (B2), keine Annahme.**
- Grenzen: Jev erzeugt keinen Text, ruft keine Werkzeuge, liest keine Dokumente, zitiert nicht. Untersuchung, Belege und Testvorschlag bleiben beim Agenten. Anbieter ist jung (09/2026, Early Access); alles läuft ohne ihn weiter.

## 5. Schicht 4 – Mensch in der Schleife
- Belege einzeln **ablehnen** (Grund wählbar), gespeichert mit Trace-ID.
- Test **freigeben** → `POST /retest` im Twin (nachdem die Störung behoben wurde – im Demo per Knopf „Station abgekühlt") → Ergebnis wird mit der Vorhersage aus `simulate_retest` verglichen → `outcome: supported | refuted | inconclusive` → Akte.
- Der Unterschied Simulation/Realität ist im UI immer sichtbar (Beschriftung „Simulation (Modell)" vs. „Re-Test (Twin-Messung)").

## 6. Schicht 0 – Evals und Observability
- `evals/bench.py`: lädt Szenarien, injiziert Störungen, wartet `settle_s`, prüft Lösbarkeit, ruft System (B0/B1/V1/V2) n-mal, misst alle Metriken, schreibt `data/evals/bench-<ts>.json` und eine Markdown-Tabelle (`design/RESULTS.md`).
- Judge: separates Modell (Haiku, sobald verfügbar; sonst gpt-5-mini mit Vermerk).
- Latenz-Attribution aus Jaeger-Spans: Modellzeit vs. Werkzeugzeit je Lauf.

## 7. Entscheidungen (ADR-Kurzform)

| # | Entscheidung | Begründung |
|---|---|---|
| A1 | Ein Agent, kein Orchestrator | Westermo: 3× Zeit, 2× Kosten, kein Qualitätsgewinn |
| A2 | Deterministische Werkzeuge vor dem Modell | CausalPulse, KG-HiL, Sensor-Level; Pitfall-Studie 71 % |
| A3 | Verifikationsmodul statt Prompt-Tuning | Pitfall-Studie: Prompts halfen nicht, Verifikation half |
| A4 | Evidenzstärke statt Konfidenzzahl | Westermo: Confidence nicht interpretierbar |
| A5 | Simulation ≠ Bestätigung; Re-Test ist die Bestätigung | Prozessanlagen-Paper; Ingenieurspraxis (8D D4/D6) |
| A6 | Benchmark mit Wahrheit, Lösbarkeitsfilter, Wiederholungen, Baselines | TraceBench, CoffeeBench, Westermo |
| A7 | Spezifikation maschinenlesbar neben Markdown, aus Markdown generiert | AAS-Idee im Kleinen; Konsistenz testbar |
| A8 | Provider-Abstraktion bleibt; Modellwahl ist Benchmark-Ergebnis | TraceBench: Modelle unterscheiden sich stark in Kosten/Genauigkeit |
| A9 | System-One-Modell (Jev) nur für Routing/Triage, hinter Schalter, als Ergänzung | Westermo (Confidence-Problem); Anbieterrisiko → optional. Die Router-Idee ist zusätzlich im Lagerdiagnose-Paper beschrieben (nur Abstract gelesen) – die Entscheidung hängt nicht von dessen Zahlen ab. |

## 8. Dateiplan (neu / geändert)

```
docs/spec/TS-DCU-EOL.json, TS-DCU-EOL.rev-C.json     (2.2)
docs/TS-DCU-EOL.rev-C.md  (superseded, für S10)        (2.3)
src/ecu_copilot/twin/{models,simulator,api}.py          (2.1: sensor_offset, firmware_change, fixture_fault, /retest, /simulate)
src/ecu_copilot/engineering/{spec,validity,change,cluster,describe,simulate}.py   (3)
src/ecu_copilot/copilot/tools.py                        (3: neue Tools)
src/ecu_copilot/copilot/verify.py                       (4.2)
src/ecu_copilot/copilot/agent.py                        (4.1: Schema, Prompt-Regeln)
src/ecu_copilot/copilot/api.py                          (5: /evidence-feedback, /retest-Weiterleitung, outcomes)
evals/scenarios/*.json, evals/bench.py, evals/baselines.py   (6)
tests/test_engineering.py, tests/test_verify.py, tests/test_scenarios_consistency.py
design/RESULTS.md                                       (Benchmark-Ergebnisse, fortgeschrieben)
```
