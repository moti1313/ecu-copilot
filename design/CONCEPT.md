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

Ziel: 20 Szenarien, je 3 Läufe → 60 Läufe pro System, ca. 3–5 $ pro vollständigem Vergleich (gpt-5) – oder weniger mit kleinerem Modell.

## 5. Baselines und Metriken

**Systeme im Vergleich**
- **B0 – Regelwerk:** deterministische Werkzeuge + feste Entscheidungsregeln (E-204 ∧ T1 > 32 → Pseudo usw.), kein LLM. *Zeigt ehrlich, was ohne KI geht.*
- **B1 – Einmal-RAG:** ein Modellaufruf mit Statistik + Top-5-Chunks im Prompt, keine Werkzeuge. *Der „Chatbot".*
- **V1 – heutiger Agent.**
- **V2 – Agent mit deterministischen Werkzeugen, Belegprüfung, Testplanung.**

**Metriken je Lauf**
| Metrik | Definition |
|---|---|
| Befund-Genauigkeit | `finding` = Wahrheit (pseudo/echt/unklar/information) |
| Ursachen-Genauigkeit | Komponente/Los/Ursache in `affected_components` bzw. Hypothese 1 |
| Test-Korrektheit | vorgeschlagener Test entspricht dem richtigen (Judge mit Rubrik) und ist **unterscheidend** |
| Zitat-Validität | Anteil Dokument-Zitate, die existieren (Dokument + Abschnitt + aktuelle Revision) |
| Beleg-Verifikation | Anteil Live-Belege, deren Zahlen in Werkzeugausgaben vorkommen |
| Explorations-Vollständigkeit | Pflicht-Werkzeuge des Szenarios aufgerufen |
| Konsistenz | Anteil gleicher Befunde über 3 Läufe |
| Latenz, Kosten | Sekunden, USD |

**Erwartung (ehrlich):** B0 wird S01–S03 lösen und bei S04–S10 versagen (kennt die Fälle nicht). B1 wird plausibel klingen und bei Zitat-Validität und Mehrfachursachen einbrechen. V2 soll V1 bei Beleg-Verifikation, Konsistenz und S05/S08/S10 schlagen – wenn nicht, sagen wir das.

## 6. Nicht-Ziele (bewusst)
- Kein Multi-Agent-System, solange Evals es nicht verlangen.
- Keine Feinjustierung von Modellen.
- Keine neue Simulationsphysik; der Twin bleibt ein Datenerzeuger mit Zustand.
- Keine Echtzeit-Streaming-Architektur (Kafka) – Erwähnung im README reicht.
- Keine weiteren Oberflächen (B/C) vor Abschluss von Phase 1–2.

## 7. Phasen und Abnahmekriterien

| Phase | Inhalt | Abnahme („fertig, wenn") | Aufwand |
|---|---|---|---|
| **1 – Evidenz & Messung** | maschinenlesbare Spezifikation; Werkzeuge `check_validity`, `detect_change`, `cluster_failures`, `describe_signal`; Belegprüfung; Szenario-Bank (12 Szenarien); Harness mit Wiederholungen; Baselines B0/B1 | Eine Tabelle V1 vs. V2 vs. B0 vs. B1 über 12 Szenarien × 3 Läufe, alle Metriken aus §5; Beleg-Verifikation im UI sichtbar | 2–3 Tage |
| **2 – Hypothesentest** | `simulate_retest` im Twin; `POST /retest` (echter Re-Test im Twin nach Freigabe); Ergebnis gegen Vorhersage; Protokoll; UI-Integration | S01 Ende-zu-Ende: Vorhersage → Freigabe → Re-Test → „gestützt", mit Trace; Szenario S05 unterscheidet Sensorfehler | 2 Tage |
| **3 – Versionen & Robustheit** | Dokument-Revisionen im RAG; Szenarien S06, S10; Latenz-Analyse aus Jaeger, Effort/Modell-Vergleich | S10 besteht; Latenz-Tabelle (Modell × Effort) | 1–2 Tage |
| **4 – Demo-Fluss** | Leitstand-Sicht (B) und Akte (C) als Einstieg/Ausstieg; Drehbuch | 5-Minuten-Demo läuft zweimal ohne Eingriff | 1–2 Tage |

Reihenfolge ist fix: **erst messen (1), dann testen (2), dann schön (4).**

## 8. Offene Entscheidungen
1. Modell für den Benchmark: gpt-5 (teurer, 60 Läufe ≈ 4 $) oder gpt-5-mini (≈ 1 $, evtl. schlechter)? Vorschlag: beide, das ist selbst ein Ergebnis.
2. Judge: gpt-5-mini (gleiche Familie) oder – bei verfügbarem unabhängigem Modellzugang – claude-haiku als unabhängiger Judge? Vorschlag: Haiku, wenn verfügbar.
3. Soll der Twin Firmware-Version und Sensor-Offset als Störungstypen bekommen (für S05/S06)? Vorschlag: ja, es sind ~40 Zeilen.
