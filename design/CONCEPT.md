# Konzept V2 – Evidence-Driven EOL Investigator

*„Vom Testfehler zur belegten Ingenieursentscheidung"*

Status: Entwurf zur Abstimmung (16.10.2026). Dieses Dokument und `ARCHITECTURE.md` sind der **Vertrag** für die Implementierung: Was nicht hier steht, wird nicht gebaut; was hier steht, hat ein Abnahmekriterium.

---

## 1. Problem (eine Frage, kein Themenfeld)

> Ein EOL-Prüfstand meldet steigende Ausfälle. **Liegt es am Gerät – oder an Prüfbedingungen, Messtechnik, Prüfsoftware oder Material-Los?** Welche Belege stützen welche Erklärung, welcher Test trennt sie, und was entscheidet der Ingenieur?

Das ist bewusst enger als „Root Cause Analysis". Es ist das Problem, das ein Automobilzulieferer bei seiner Akustikprüfung öffentlich beschrieben hat (95 % Pseudo-Fehler), und das die Westermo-Studie als Kernfrage industrieller Testanalyse identifiziert.

## 2. Was V2 anders macht als V1 (die drei Unterschiede)

| | V1 (heute) | V2 |
|---|---|---|
| **Wer rechnet** | Das Modell liest Statistik-JSON und entscheidet über Gültigkeit und Trend | **Deterministische Werkzeuge** liefern geprüfte Evidenz: Gültigkeit je Messung, Änderungszeitpunkt, Los-Cluster, Signal-Deskriptoren. Das Modell integriert und erklärt. |
| **Was mit Belegen passiert** | Belege stehen im Report, niemand prüft sie | **Belegprüfung:** jede Zahl gegen Werkzeugausgaben, jedes Zitat gegen den Index (Dokument, Abschnitt, Revision). Ergebnis sichtbar: „7 von 8 Belegen verifiziert". |
| **Was mit Hypothesen passiert** | Hypothese + Textvorschlag für einen Test | **Hypothesentest:** Vorhersage im Twin simulieren → Ingenieur gibt frei → Re-Test im Twin ausführen → Ergebnis gegen Vorhersage → „gestützt / widerlegt", protokolliert. |

Dazu: **Qualität wird gemessen** – Szenario-Benchmark mit Wahrheit, drei Baselines, Wiederholungen.

## 3. Nutzer und Workflow

**Nutzer:** Prüfingenieur / Testexperte Fertigungstechnologie (die Rolle aus der öffentlichen Meldung zur Akustikprüfung). Kein Werker, kein Manager.

**Workflow (unverändert aus den Design-Konzepten A/B/C):**
1. Störung tritt auf → Signal zeigt sie (Leitstand-Sicht, später).
2. Ingenieur stellt die Frage oder klickt „Untersuchen" (Arbeitsplatz, Konzept A).
3. Agent sammelt Evidenz mit Werkzeugen, formuliert Hypothesen, schlägt einen **unterscheidenden** Test vor, zeigt die **Twin-Vorhersage** („Simulation").
4. Ingenieur prüft Belege (verifiziert ✓ / nicht verifiziert ✗ / abgelehnt), gibt Test frei oder lehnt ab.
5. Test läuft (im Twin), Ergebnis wird gegen Vorhersage gehalten, Hypothese wird „gestützt" oder „widerlegt"; alles landet in der Akte (Konzept C, später).

## 4. Szenario-Bank (das Herz der Bewertung)

Jedes Szenario: Störung(en) im Twin + Frage + **Wahrheit** (Befundtyp, Ursache, betroffene Komponente/Los, richtiger nächster Test, Pflicht-Belege) + Lösbarkeitskriterium (Effektgröße groß genug, damit die Antwort eindeutig ist – nach TraceBench).

| # | Szenario | Wahrheit | Was es prüft |
|---|---|---|---|
| S01 | Temperaturdrift St. 2 | Pseudo · T1 > 32 °C · U1/T1 · Re-Test nach Abkühlung | Kernfall |
| S02 | Hallenlärm St. 3 | Pseudo · Lärm > 45 dB · MIC · Re-Test bei Ruhe | zweite Umgebungsursache |
| S03 | Schlechtes Steckverbinder-Los | Echt · Los L2439-07 · J3 · Los sperren, Trennung | echter Fehler, Los-Cluster |
| S04 | **Kein Fehler** (Frage behauptet Anstieg) | Information/unklar · „kein Anstieg" | Agent darf nicht erfinden |
| S05 | **Defekter T1-Sensor** (zeigt +8 K, Iq unverändert) | Unklar/Messtechnik · Iq folgt T1 nicht · T1 · Sensor prüfen | Korrelation ≠ Kausalität |
| S06 | **Firmware 3.5 ausgerollt** (größeres Image → E-401 auf B) | Echt (Prüfsoftware) · Firmware-Version · SERVICE_IF · Flash-Limit prüfen | Versionsbezug |
| S07 | Fixture-Defekt St. 2 (E-205 über A **und** B) | Pseudo/Station · FIXTURE · Fixture-Selbsttest | Variantenübergreifendes Muster |
| S08 | Drift **und** schlechtes Los gleichzeitig | Beides · zwei Hypothesen getrennt | Mehrfachursache |
| S09 | Drift auf St. 1 (Variante A, näher am Rand als erwartet?) | Pseudo, geringe Rate | Schwaches Signal, Lösbarkeit grenzwertig |
| S10 | **Veraltete Spezifikation** (Rev. C mit 400 µA im Index) | Antwort muss Rev. D (450 µA) nutzen und Rev. C als überholt nennen | Dokumentversionierung |
| S11–S15 | Informationsfragen (Limits, Abkündigung, 8D-Inhalt, Nicht-existenter Grenzwert, Off-Topic) | wie V1-Golden-Set | Grundfunktion |
| S16–S20 | Varianten von S01–S03 mit anderen Stationen/Stärken, 2 Wiederholungen je Szenario | Konsistenz | Varianz messen |

Umfang: **Phase 1 = 12 Szenarien** (S01–S05, S08, S11–S15, S04), **Endausbau = 20** (plus S06, S07, S09, S10, S16–S20). Je 3 Läufe → 36 bzw. 60 Läufe pro System; ca. 2–5 $ pro vollständigem Vergleich mit gpt-5, weniger mit gpt-5-mini.

**Unklare Fälle bleiben drin:** S04 (kein Fehler), S05 (Sensor) und S09 (schwaches Signal) haben die Wahrheit „unklar/kein Befund". Richtiges **Zurückhalten** einer Diagnose wird als Treffer gewertet; eine selbstbewusste Falschdiagnose zählt doppelt negativ (Befund falsch *und* nicht zurückgehalten).

## 5. Baselines und Metriken

**Systeme im Vergleich**
- **B0 – Regelwerk:** deterministische Werkzeuge + feste Entscheidungsregeln (E-204 ∧ T1 > 32 → Pseudo usw.), kein LLM. *Zeigt ehrlich, was ohne KI geht.*
- **B1 – Einmal-RAG:** ein Modellaufruf mit Statistik + Top-5-Chunks im Prompt, keine Werkzeuge. *Der „Chatbot".*
- **V1 – heutiger Agent.**
- **V2 – Agent mit deterministischen Werkzeugen, Belegprüfung, Testplanung.**

**Metriken je Lauf**
| Metrik | Definition |
|---|---|
| Befund-Genauigkeit | je `assessment`: `test_validity` und `defect_indication` = Wahrheit für die betroffene Gruppe; bei Mehrfachfehlern müssen **beide** Gruppen stimmen |
| Ursachen-Genauigkeit | `root_cause` aus dem kontrollierten Vokabular = Wahrheit |
| Zurückhaltung | bei Wahrheit „unklar": Agent sagt unklar (Treffer) statt zu raten |
| Test-Korrektheit | vorgeschlagener Test entspricht dem richtigen (Judge mit Rubrik) und ist **unterscheidend** |
| Zitat-Validität | Anteil Dokument-Zitate mit existierendem Dokument + Abschnitt + aktueller Revision |
| Herkunfts-Rate | Anteil Live-Belege, deren `ref` (Aufruf, Feld, Station, Variante, Fenster, Wert) in den Werkzeugausgaben dieses Laufs stimmt |
| Stützungs-Rate | Anteil Belege, bei denen die Behauptung zum referenzierten Wert/Abschnitt passt (deterministisch, wo möglich; sonst „nicht geprüft") |
| Explorations-Vollständigkeit | Pflicht-Werkzeuge des Szenarios aufgerufen |
| Konsistenz | Anteil gleicher Befunde über 3 Läufe |
| Latenz, Kosten | Sekunden, USD |

**Erwartung (ehrlich):** B0 bekommt dieselben Werkzeuge wie V2 und Regeln für alle bekannten Muster (Temperatur, Lärm, Los-Lift, Sensor-Entkopplung, Firmware, Fixture). Es wird S01–S03, S05–S07 vermutlich lösen und bei Informationsfragen, Mehrfachursachen mit Interaktion und Fragen außerhalb seines Regelsatzes versagen. B1 wird plausibel klingen und bei Zitat-Validität und Herkunft einbrechen. V2 muss sich gegen **dieses** B0 beweisen – schlägt es B0 nur dort, wo B0 keine Regel hat, ist das ein ehrliches und nützliches Ergebnis („Regeln für bekannte Muster, Agent für den Rest").

## 6. Nicht-Ziele (bewusst)
- Kein Multi-Agent-System, solange Evals es nicht verlangen.
- Keine Feinjustierung von Modellen.
- Keine neue Simulationsphysik; der Twin bleibt ein Datenerzeuger mit Zustand.
- Keine Echtzeit-Streaming-Architektur (Kafka) – Erwähnung im README reicht.
- Keine weiteren Oberflächen (B/C) vor Abschluss von Phase 1–2.

## 7. Phasen und Abnahmekriterien

| Phase | Inhalt | Abnahme („fertig, wenn") | Aufwand |
|---|---|---|---|
| **0 – Korrekturen aus dem Review (16.10.)** | (a) UI sagt nur, was das Backend tut: „Entscheidung protokolliert", nicht „Sperrung veranlasst"; HTTP-Status prüfen. (b) Eval-Gate: übersprungene Live-Fälle zählen als nicht bestanden. (c) Simulator: Lese-Snapshots unter Lock. (d) Freigaben an eine serverseitig gespeicherte Untersuchung (`investigation_id`) binden. (e) Prompt-Regel: **„ungültige Prüfung ≠ fehlerfreies Bauteil"** – Befund „Pseudo-Fehler" heißt „keine belastbare Bauteilbewertung möglich, Wiederholung unter gültigen Bedingungen", nie „Bauteil in Ordnung". | Tests für (b), (c), (d); S08 (gleichzeitige Fehler) im Golden-Set | ½ Tag |
| **1 – Evidenz & Messung** | maschinenlesbare Spezifikation **mit Revision und Status** (Minimalversionierung, damit die Herkunftsprüfung „aktuelle Revision" prüfen kann); Werkzeuge `check_validity`, `detect_change`, `cluster_failures` (mit Lift), `describe_signal`; Report-Schema V2 (`assessments`, strukturierte `ref`); Belegprüfung (Herkunft + Stützung); Szenario-Bank (12 Szenarien inkl. S08); Harness mit Wiederholungen; Baselines B0 (fair) / B1. **Erster Durchstich: S01 und S08 vollständig.** | Eine Tabelle V1 vs. V2 vs. B0 vs. B1 über 12 Szenarien × 3 Läufe, alle Metriken aus §5; Herkunft/Stützung je Beleg im UI sichtbar | 3 Tage |
| **2 – Hypothesentest** | Twin mit **persistentem Einheit-Zustand** (Serial → latenter Defekt, individueller Offset); `simulate_retest` (Modellpfad) und `POST /retest` (Messpfad, dieselben Einheiten) als getrennte Wege; Ergebnis gegen Vorhersage; Protokoll; UI-Integration | S01 Ende-zu-Ende: Vorhersage → Freigabe → Re-Test → „gestützt"; **S08: Re-Test nach Abkühlung lässt die Los-Einheiten weiterhin durchfallen** (Defekt persistiert); Szenario S05 unterscheidet Sensorfehler | 2 Tage |
| **3 – Versionen & Robustheit** | vollständige Dokument-Revisionen im RAG (superseded-Dokumente im Index, Filter); Szenarien S06, S07, S09, S10, S16–S20; Latenz-Analyse aus Jaeger, Effort/Modell-Vergleich | S10 besteht; Benchmark auf 20 Szenarien; Latenz-Tabelle (Modell × Effort) | 1–2 Tage |
| **4 – Demo-Fluss** | Leitstand-Sicht (B) und Akte (C) als Einstieg/Ausstieg; Drehbuch | 5-Minuten-Demo läuft zweimal ohne Eingriff | 1–2 Tage |

Reihenfolge ist fix: **erst messen (1), dann testen (2), dann schön (4).**

## 8. Entscheidungen vom 16.10.2026
- **Phase 0 starten**, danach **S01 und S08 vollständig und reproduzierbar** (Phase-1-Durchstich), erst dann der Rest.
- **Jev zurückgestellt.** Bleibt als Option in `ARCHITECTURE.md` §4.4 beschrieben, wird vor Abschluss von Phase 2 nicht gebaut.
- Die vier Punkte aus Review 2 (strukturierte Belegzuordnung, getrennte Bewertung von Prüfgültigkeit und Bauteilfehler, faire Baselines mit Bezugsgrößen, Re-Test derselben Einheiten mit erhaltenen Defekten) sind in §5 (Metriken) und §7 (Abnahme Phase 1/2) und in `ARCHITECTURE.md` §3/§4 festgehalten.

## 9. Noch offene Entscheidungen (blockieren Phase 0/1 nicht)
1. Modell für den Benchmark: gpt-5 (teurer, 60 Läufe ≈ 4 $) oder gpt-5-mini (≈ 1 $, evtl. schlechter)? Vorschlag: beide, das ist selbst ein Ergebnis.
2. Judge: gpt-5-mini (gleiche Familie) oder – bei verfügbarem unabhängigem Modellzugang – claude-haiku als unabhängiger Judge? Vorschlag: Haiku, wenn verfügbar.
3. Soll der Twin Firmware-Version und Sensor-Offset als Störungstypen bekommen (für S05/S06)? Vorschlag: ja, es sind ~40 Zeilen.
