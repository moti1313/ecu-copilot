# Architektur V2 – ECU Copilot

Status: Entwurf zur Abstimmung (16.10.2026). Ergänzt `CONCEPT.md`; Begründungen in `RESEARCH.md`, Ist-Zustand in `AUDIT.md`.

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
| `simulate_retest(serials, conditions)` | Serials + Zielbedingungen (z. B. board_temp_c=25) | vorhergesagtes Ergebnis je Einheit aus dem Leckstrommodell, klar markiert `simulation: true`, mit Modellannahmen | Prozessanlagen-Paper: Twin-Validierung vor Maßnahme |
| `search_docs`, `lookup_part`, `draft_8d_report` | wie V1 | + Revision in Zitaten | – |

`get_station_stats` bleibt; `get_recent_results` wird auf max. 40 Ergebnisse begrenzt und liefert die Zusammenfassung zuerst.

## 4. Schicht 3 – Agent und Verifikation

### 4.1 Agent
Unverändert ein Agent (Anthropic Tool Runner / OpenAI-Loop), Report-Schema wie V1 plus:
- `hypotheses[].test`: `{title, discriminates: ["H1","H2"], prediction_if_true, prediction_if_false}` – der Test muss sagen, welche Hypothesen er trennt (CoffeeBench).
- `evidence[].values`: die Zahlen des Belegs als Liste (für die Prüfung).
- `routing`: `["live","docs"]` – welche Pfade der Agent für die Frage gewählt hat (Router-Idee aus dem Lager-Paper; macht die Entscheidung messbar).

Prompt-Regeln neu: „Benutze `check_validity`, bevor du über Gültigkeit sprichst. Benutze `detect_change`, bevor du ‚seit X Minuten' sagst. Rechne nicht selbst."

### 4.2 Verifikationsmodul (`copilot/verify.py`)
Läuft nach dem Modell, vor der Antwort. Kein LLM.
- **Live-Belege:** jede Zahl in `values` muss in einer Werkzeugausgabe desselben Laufs vorkommen (Toleranz 1 % oder Rundung). Ergebnis je Beleg: `verified` / `not_found`.
- **Dokument-Belege:** Zitat parsen (doc_id, revision, section) → existiert der Chunk? Ist die Revision `current`? → `verified` / `unknown_section` / `superseded`.
- **Report-Ebene:** `verification: {live_verified: n/m, docs_verified: n/m, flags: [...]}`. Bei `live_verified < 100 %` erscheint eine Warnung im UI; bei erfundenem Zitat wird der Beleg rot.
- Metrik fließt in Evals ein (Beleg-Verifikation, Zitat-Validität).

### 4.3 Baselines (`evals/baselines.py`)
- **B0:** ruft Schicht 2 direkt, Entscheidungsbaum: `check_validity` → wenn INVALID-Anteil > 50 % → Pseudo; sonst `cluster_failures(by=lot)` → Konzentration > 0,5 → Echt/Los; sonst unklar. Kein LLM.
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
| A9 | System-One-Modell (Jev) nur für Routing/Triage, hinter Schalter, als Ergänzung | Lagerdiagnose-Paper (Router); Westermo (Confidence-Problem); Anbieterrisiko → optional |

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
