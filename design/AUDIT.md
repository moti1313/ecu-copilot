# Architektur-Audit ECU Copilot V1 (Stand 16.10.2026, Commit 3f1199e)

Zweck: Ehrlich festhalten, **was implementiert, was getestet und was nur behauptet** ist. Grundlage für das V2-Konzept. Drei Stufen: ✅ unit-getestet · 🟡 nur manuell/einmalig geprüft · ❌ nicht geprüft oder nicht vorhanden.

## 1. Was existiert und wie es geprüft ist

| Baustein | Umsetzung | Prüfstand |
|---|---|---|
| **Twin** – Simulator (3 Stationen, 2 Varianten, Leckstrommodell, 3 Störungen, Stats, Serien) | `twin/simulator.py`, `twin/api.py`, `twin/models.py` | ✅ 11 Tests (Ausfallrate unter Drift/Lärm/Los, Validierung, Serien-Buckets) · Docker healthy |
| **RAG** – Abschnitts-Chunking, fastembed + Chroma + BM25, RRF | `rag/chunking.py`, `rag/index.py`, `rag/ingest.py` | ✅ BM25-Pfad 4 Tests · 🟡 Hybrid-Pfad nur manuell (5 deutsche Fragen, Treffer korrekt) |
| **Tools** – search_docs, get_station_stats, get_recent_results, lookup_part, draft_8d_report | `copilot/tools.py` | ✅ 5 Tests (mit Fake-Twin, Fehlerpfade, Schema strict) |
| **Agent** – Anthropic Tool Runner und OpenAI-Loop, strukturierter Report, Guardrails, Accounting | `copilot/agent.py` | ✅ 8 Tests mit Fake-Clients (Accounting, Guardrail, Abbruch, Parsing) · 🟡 **OpenAI live:** 1 voller Eval-Lauf (9/10) + 2 Einzelläufe · ❌ **Anthropic live: nie gelaufen** |
| **Monitoring** – OTel → Jaeger, Metrik-Log, Kosten | `copilot/telemetry.py`, `copilot/metrics.py` | 🟡 Jaeger empfängt Traces (gesehen), Kostenrechnung ✅ getestet |
| **Evals** – 10 Fälle, Tools → Fakten → Judge, CI-Gate | `evals/golden.json`, `evals/run.py` | 🟡 1 Lauf, 9/10 (der 10. war ein Fehler des Prüfers, behoben). **Keine Wiederholung, keine Varianz, keine Baseline.** |
| **UI** – Signalstreifen, Schema, Hypothesen/Belege, Freigabe | `copilot/static/index.html` | 🟡 JavaScript-Syntax geprüft; Endpunkte geprüft; **im Browser nur die Vorversion gesehen** |
| **Freigaben** – `POST /decisions` mit Trace-ID | `copilot/api.py` | ✅ 1 Test |
| **Container/CI** | Dockerfile, Compose, GitLab-CI, GitHub Actions | 🟡 Compose-Stack läuft; **CI-Pipelines nie ausgeführt** (kein GitLab; GitHub Actions nicht aktiviert) |

Zahlen: 34 Unit-Tests grün, ruff sauber, 2 echte Eval-Läufe (0,34 $ + Einzelfälle), Latenz 7–80 s je Frage, Kosten 0,5–9 Cent je Frage (gpt-5).

## 2. Was fehlt – nach Schwere geordnet

### 2.1 Der Agent rechnet selbst (Risiko: halluzinierte Interpretation)
Die Entscheidung „Messung außerhalb 18–32 °C = ungültig" trifft das Modell, indem es Statistik-JSON liest und mit einem Dokumentabschnitt vergleicht. Das hat im Eval funktioniert – aber die Literatur (71 % halluzinierte Interpretation, über alle Modelle) sagt, dass genau hier die Fehler entstehen. **Es gibt keine deterministische Gültigkeitsprüfung, keine Änderungserkennung, keine Los-Clusterung als Werkzeug.** Der Agent muss „seit 10 Minuten" selbst über zwei Fenster schätzen.

### 2.2 Belege werden nicht verifiziert
Der Report enthält Belege mit Zahlen und Zitaten. **Niemand prüft**, ob die Zahl in einer Werkzeugausgabe vorkommt oder ob „TS-DCU-EOL §4.2" existiert. Der Zitier-Guardrail ist ein Regex auf Dokumentnamen – „TS-DCU-EOL §9.9" würde durchgehen.

### 2.3 Hypothesen werden nicht getestet
`next_test` ist Text. Es gibt keinen Weg, die Vorhersage („7/7 bestehen nach Abkühlung") im Twin zu simulieren oder den echten Re-Test auszuführen und das Ergebnis gegen die Vorhersage zu halten. Die Freigabe wird protokolliert, **das Ergebnis nicht.**

### 2.4 Evaluation ist zu klein, um etwas zu beweisen
- 10 Fälle, davon 3 Live-Szenarien, je 1 Lauf. Keine Aussage über Konsistenz.
- Keine Baseline: Wir wissen nicht, ob ein Regelwerk („E-204 und T1 > 32 °C → Pseudo") dasselbe leisten würde – vermutlich ja, für die drei eingebauten Störungen.
- Judge ist dieselbe Modellfamilie wie der Agent.
- Live-Fälle hängen von Wartezeiten ab (Settle 90–150 s); Timing beeinflusst das Ergebnis.
- Nur 3 Störungsarten. **Fehlende Szenarien:** defekter Sensor (T1 zeigt falsch), Firmware-Wechsel, veraltetes Dokument, Fixture-Defekt, gleichzeitige Störungen, **kein Fehler** (Agent muss „nichts Auffälliges" sagen).

### 2.5 Dokumente haben keine Versionen
Front matter trägt `revision`, aber Retrieval ignoriert sie. Ein veraltetes Dokument mit altem Grenzwert würde gleichberechtigt gefunden. Zitate enthalten keine Revision.

### 2.6 Kleinere Punkte
- Anthropic-Pfad: Tool-Dauer wird pro Batch geschätzt; Prompt Caching nicht live geprüft.
- Latenz 25–80 s ohne Streaming; keine Messung, wo die Zeit hingeht (Jaeger hat die Daten, niemand hat sie ausgewertet).
- Twin: CORS offen, keine Auth – für einen Prototyp in Ordnung, muss im README stehen.
- `get_recent_results` liefert bis 200 Rohergebnisse ins Modell – teuer und genau das, wovon die Literatur abrät.
- UI: Cursor-Synchronisation nur für T1/U1; Belege sind nicht zeitlich verknüpft.
- Keine Mehrrunden-Konversation (jede Frage startet bei null).

## 3. Was V1 richtig gemacht hat (nicht anfassen)
- Strukturierter Report mit Evidenzstärke statt Konfidenzzahl – deckt sich mit Westermo.
- Single-Agent mit wenigen, klar beschriebenen Tools – deckt sich mit Westermo.
- Tests ohne API-Key, Evals mit Gate, Kosten pro Frage sichtbar.
- Provider-Abstraktion.
- Twin hinter REST, Story mit absichtlicher Firmware-Lücke.

## 4. Bewertung in einem Satz
V1 ist ein **sauber gebauter Prototyp einer Agent-Anwendung** mit guter Betriebs-Hygiene – aber als **Diagnosesystem** verlässt er sich noch auf das Modell, wo die Literatur deterministische Werkzeuge und Verifikation verlangt, und seine Qualität ist nicht nachgewiesen, nur plausibel.
