# Forschungsreview – LLM-Agenten für industrielle Fehleranalyse (Stand 16.10.2026)

Zweck: Nicht „Ideen sammeln", sondern **belegen, welche Entscheidungen im ECU Copilot V2 durch Literatur gedeckt sind** – und welche Fehler andere schon gemacht haben. Jede Quelle: Was wurde gebaut, wie wurde gemessen, was nehmen wir mit. Alle Links geprüft am 16.10.2026.

---

## 1. Die wichtigsten fünf Arbeiten

### 1.1 Westermo: *Supporting Industrial Test-Failure Analysis with LLM-Based Systems* (arXiv 2609.21843, Sept. 2026)
[arxiv.org/abs/2609.21843](https://arxiv.org/abs/2609.21843) – Jansson, Strandberg, Sörensen, Enoiu, Afzal (Westermo Network Technologies, Mälardalen University)

- **Problem:** Nächtliche Regressionstests schlagen fehl; Ingenieure müssen aus Logs und Metadaten entscheiden: Produktsoftware, Testframework, Testumgebung oder Zusammenspiel? *Exakt unsere Frage: Gerät oder Prüfumgebung.*
- **Gebaut:** Single-Agent (ein Agent, drei Tools über MCP) vs. Multi-Agent (Orchestrator + 4 Subagenten). GPT-5.4, LangChain Deep Agents. Report-Struktur: Root Cause, Confidence, **Evidence**, Reasoning Steps, Next Steps, Assumptions, Limitations.
- **Gemessen:** 2 reale Szenarien, 6 Praktiker (Survey + Fokusgruppe), 30 Läufe pro Szenario und Architektur (120 Läufe): Dauer, Kosten, Konsistenz (Anteil semantisch gleicher Schlussfolgerungen).
- **Ergebnis:** Single-Agent ≈ 40 s, Multi-Agent ≈ 130 s; Kosten halb so hoch; Konsistenz höher. **Kein konsistenter Qualitätsvorteil des Multi-Agent-Systems.** Praktiker schätzten den **Evidence-Abschnitt am meisten** – auch wenn sie die Root Cause ablehnten. „Reasoning Steps" wirkten unnatürlich. **Confidence-Wert war nicht interpretierbar.** Plausible, aber falsche Schlussfolgerungen lenkten Untersuchungen in die Irre.
- **Empfehlungen der Autoren:** Mit Single-Agent beginnen; **Evidenz-Entdeckung über definitive Diagnose stellen**; Schlussfolgerungen als Hypothesen mit inspizierbaren Belegen; Unsicherheit vorsichtig kommunizieren; Mensch bleibt verantwortlich.
- **Was wir mitnehmen:** (a) Single-Agent bleibt – Multi-Agent nur, wenn unsere Evals es rechtfertigen. (b) Evidenz ist das Produkt, nicht die Diagnose. (c) Keine numerische Konfidenz – das haben wir in V1 bereits so gemacht (Evidenzstärke). (d) **Konsistenz über wiederholte Läufe** als Metrik aufnehmen (haben wir noch nicht).

### 1.2 CausalPulse: *Agentic Copilot for Root Cause Analysis in Smart Manufacturing* (AAAI-26 Demo; Langfassung arXiv 2603.29755)
[ojs.aaai.org/…/42381](https://ojs.aaai.org/index.php/AAAI/article/view/42381) · [arxiv.org/abs/2603.29755](https://arxiv.org/abs/2603.29755) – Shyalika et al.

- **Gebaut:** Neurosymbolischer Multi-Agent-Copilot: Vorverarbeitung → Anomalieerkennung → **kausale Entdeckung** → RCA; Orchestrierung über MCP/A2A/LangGraph. Human-in-the-loop-Design.
- **Gemessen:** Future-Factories-Datensatz (öffentlich) und ein proprietärer Sensor-Datensatz; „Erfolgsrate" 98 % (Definition im Abstract nicht angegeben); **50–60 s Latenz pro Diagnose-Workflow**; wird in einem **Bosch-Werk** eingeführt.
- **Was wir mitnehmen:** (a) Die Agenten rufen **echte analytische Werkzeuge** auf (Anomalieerkennung, Kausalanalyse), sie „chatten" nicht über Rohdaten. Unser V1 lässt das Modell Statistik-JSON selbst interpretieren – das ist die Schwachstelle. (b) 50–60 s Latenz gilt dort als akzeptabel für eine Diagnose – unsere 25–80 s sind im Rahmen, aber wir sollten es messen und senken. (c) Zur Einordnung: Bosch (Mechatronik-Zulieferer) setzt genau diese Klasse von System ein.

### 1.3 *Why Do AI Agents Systematically Fail at Cloud Root Cause Analysis?* (arXiv 2602.09937, Feb. 2026)
[arxiv.org/abs/2602.09937](https://arxiv.org/html/2602.09937v2)

- **Gemessen:** 1.675 Agentenläufe auf OpenRCA (335 Vorfälle), 5 Modelle; jede Fehlklassifikation von Menschen verifiziert.
- **Fehlertaxonomie (Häufigkeit über alle Läufe):** **Halluzinierte Interpretation 71 %** (der Agent legt eine kohärente Geschichte über Daten, die sie nicht hergeben) · **unvollständige Exploration 64 %** · **Symptom als Ursache 40 %** · Code-Fehler 27 % · nur eine Datenquelle 27 % · **falsches Zeitfenster 23 %** · keine Gegenprüfung 19 %. Diese Muster waren **über alle Modelle gleich** – das Framework, nicht die Modellstärke, ist der Engpass.
- **Was half und was nicht:** Prompt-Engineering („Hypothesen-Prompting", „Pitfall-Hinweise") half **nicht** gegen halluzinierte Interpretation. **Architekturänderungen halfen:** Verifikationsmodule, die Interpretationen gegen Rohdaten prüfen; strukturierter Zustandsaustausch; vollständige Werkzeugausgaben statt Zusammenfassungen.
- **Was wir mitnehmen:** Das ist die wichtigste Quelle für V2. Drei konkrete Maßnahmen: (a) **Belegprüfung** – jede Zahl in einem Live-Beleg muss in einer Werkzeugausgabe vorkommen, jede Dokumentzitation muss existieren; (b) **deterministische Werkzeuge** für Zeitfenster, Änderungserkennung und Gültigkeit – der Agent darf diese nicht selbst „ausrechnen"; (c) Metrik **„Exploration vollständig?"** (wurden alle relevanten Werkzeuge gerufen?).

### 1.4 KG-geführtes RAG für erklärbare RCA in der Automotive-HiL-Validierung (arXiv 2608.11277, Aug. 2026)
[arxiv.org/abs/2608.11277](https://arxiv.org/html/2608.11277)

- **Problem:** HiL-Aufzeichnungen (Motor-Steuergerät, E-Fahrzeug); bestehende Werkzeuge markieren Anomalien, sagen aber nicht **wo** und **warum**.
- **Gebaut:** **Evidenzextraktion zuerst** – jede fehlerhafte Aufzeichnung wird mit einer gesunden Referenz verglichen (Mittelwertverschiebung, maximale Abweichung, erste Reaktionszeit, Abnormalitäts-Score pro Signal). **Nur diese kompakte Evidenz** geht ans LLM, nie Rohzeitreihen. Dazu ein Wissensgraph (Signal→Fehler, Ausbreitungsrelationen, Diagnoseregeln) und Retrieval ähnlicher historischer Fälle. Ausgabe: JSON mit Top-1/Top-3-Ort, Ausbreitungspfad, Unsicherheitsnotizen – **gegen eine feste Labelmenge validiert**.
- **Ergebnis:** Top-1 0,90 / Top-3 1,00 (ASM), offene Modelle (Gemma-3 27B), ~5 s pro Prompt. Kleine Datenbasis (13 Aufzeichnungen).
- **Was wir mitnehmen:** (a) Unser Twin sollte dem Agenten **vorverarbeitete Evidenz** liefern: „Iq-Mittel +28 % gegenüber Referenzfenster, Onset 21:38, korreliert mit T1" – nicht 100 Rohergebnisse. (b) Ausgabe gegen feste Mengen validieren (Fehlercodes, Komponenten, Befundtypen) – haben wir mit dem Schema begonnen. (c) Bauteil-Fehler-Beziehungen (unser FMEA/Fehlercode-Mapping) sind ein Mini-Wissensgraph; den sollten wir maschinenlesbar machen statt nur als Fließtext im Dokument.

### 1.5 CoffeeBench: *Can LLM Agents Efficiently Identify Appliance Faults?* (arXiv 2610.19291, Okt. 2026)
[arxiv.org/abs/2610.19291](https://arxiv.org/html/2610.19291)

- **Gebaut:** Simuliertes Gerät (Espressomaschine) mit 99 Fehlermodi, 8 Sensoren, 4 Aktionen; der Agent diagnostiziert rundenbasiert: Hypothese → Aktion → Sensor lesen. *Strukturell dasselbe wie unser Twin.*
- **Gemessen:** Genauigkeit (pass^k), erwartete Rundenzahl bis zur Diagnose, anfängliche Unsicherheit (Entropie), **Soundness** (Judge bewertet die Begründung 0–100), AUROC. 12 Modelle.
- **Ergebnis:** Beste Modelle ~60 % Erst-Trefferquote; Soundness-Score sagt Korrektheit voraus (AUROC 0,82); eine **Soundness-Prüfung vor dem Abgeben** hob die Genauigkeit eines schwachen Modells von 32 % auf 65 %; Agenten wählen Aktionen meist **bestätigend statt unterscheidend**.
- **Was wir mitnehmen:** (a) Ein **Szenario-Benchmark auf dem Twin** mit bekannter Wahrheit ist der richtige Weg, Qualität zu messen – nicht 10 handgeschriebene Fragen. (b) „Nächster Test" soll **unterscheidend** sein (Hypothese A vs. B trennen), nicht nur bestätigend – ein Kriterium für unsere Test-Planung. (c) Eine Begründungsprüfung vor der Antwort ist billig und wirksam.

## 2. Weitere relevante Arbeiten (kürzer)

| Quelle | Kern | Für uns |
|---|---|---|
| **Digital Twin + RAG für Lagerdiagnose** – Zhu, Huang, Chen, *Applied Sciences* 16(18):9247, Sept. 2026 ([mdpi.com](https://www.mdpi.com/2076-3417/16/18/9247)) | Router schickt jede Frage in einen von vier Pfaden (unbezogen / nur Twin / nur RAG / beides); 140-Fragen-Benchmark; Router-Genauigkeit 0,98 | Unser Prompt lässt das Modell selbst entscheiden, welche Tools – das funktioniert, aber ein **expliziter Routing-Schritt** macht die Entscheidung messbar. Bestätigt unsere Kernidee: Anlagenzustand + Dokumentwissen zusammen. |
| **LLM-Agenten + Digital Twin für Störungsbehandlung in Prozessanlagen** – arXiv 2505.02076 ([arxiv](https://arxiv.org/html/2505.02076)) | Vorgeschlagene Korrekturmaßnahmen werden **erst im Twin simuliert und validiert**, dann an die Anlage gegeben; Reprompting bei Ablehnung. Klartext-Anlagenbeschreibung schlug Modelica-Code deutlich (15/15 vs. 12/15 korrekt, 5× weniger Tokens) | Grundlage für unseren **„simulierten Re-Test"**: Hypothese → Vorhersage im Twin → Freigabe → echter Re-Test → Vergleich. Und: Prompts in Klartext, nicht als Code-Dumps. |
| **TraceBench** – arXiv 2608.27182 ([arxiv](https://arxiv.org/html/2608.27182)) | Simulationsbasierte RCA-Bewertung mit kontrollierter Fehlerinjektion; **Lösbarkeitsfilter** entfernt mehrdeutige Fälle; Domänenkontext wichtigster Faktor (−20 bis −32 Punkte ohne); Beispiele brachten nichts | Für unseren Szenario-Benchmark: jedes Szenario muss **eindeutig lösbar** sein (Signal-zu-Rausch-Abstand), sonst misst man Zufall. Domänenbeschreibung im Prompt behalten. |
| **Sensor-Level Fault Diagnosis for Automotive Software Validation Using LLMs** – arXiv 2608.05921 ([arxiv](https://arxiv.org/html/2608.05921v1)) | HiL-Signale werden in **Text-Deskriptoren** (Statistik, Korrelationen, Verhalten, Kontext-Flags) übersetzt; feinjustierte 2B–8B-Modelle erreichen ~82 % | Bestätigt: Signale als **strukturierte Deskriptoren** statt Rohdaten. Unser `series`-Endpunkt liefert Rohbuckets – V2 liefert Deskriptoren. |
| **LLM-TSFD** – Zhang et al., *Expert Systems with Applications* 264 (2025), 79 Zitierungen ([ACM](https://dl.acm.org/doi/10.1016/j.eswa.2024.125861)) | Human-in-the-loop über die gesamte Pipeline (Datenvorbereitung, Kausalkorrektur, Diagnoseentscheidung) am Beispiel Stahlmetallurgie | Der Mensch ist nicht nur Freigeber am Ende, sondern korrigiert auch Zwischenschritte. Für uns: Ingenieur kann einen Beleg **ablehnen**, und das wird protokolliert. |
| **RAG für kognitive Digital Twins mit Asset Administration Shell** – *Computers in Industry* 2025 ([sciencedirect](https://www.sciencedirect.com/science/article/pii/S0166361525000958)) | Standardisierte Informationsmodelle (AAS) statt freier Dokumente; Bewertungsprotokoll für offene RAG-Antworten | Für den Industriekontext: Industrie-4.0-Standard nennen können. Für uns zu schwer; wir machen den kleinen Schritt: **maschinenlesbare Spezifikation** (Limits, Gültigkeitsfenster, Revision) neben dem Markdown. |
| **CI-gestützte HiL-Validierung mit intelligenter Fehleranalyse** – Abboush, Knieke, Rausch, *Scientific Reports* 15:32936, Sept. 2025 ([nature.com](https://www.nature.com/articles/s41598-025-21416-5)) | LSTM + DAE-k-means erkennen bekannte **und unbekannte** Fehler in HiL-Aufzeichnungen; CI-Integration | Zeigt die klassische ML-Seite (ohne LLM) – unser Baseline-Vergleich braucht eine solche regelbasierte/statistische Referenz. |

## 3. Was die Literatur zusammen sagt (Thesen für V2)

1. **Deterministisch zuerst, LLM danach.** Alle erfolgreichen Systeme (CausalPulse, KG-HiL, Sensor-Level) extrahieren Evidenz mit Code und geben dem Modell kompakte, geprüfte Fakten. Das Modell integriert und erklärt – es rechnet nicht.
2. **Verifikation statt Prompt-Tuning.** Halluzinierte Interpretation ist der häufigste Fehler (71 %) und lässt sich nicht wegprompten. Ein Verifikationsmodul, das Behauptungen gegen Werkzeugausgaben prüft, ist die wirksame Maßnahme.
3. **Single-Agent als Baseline.** Multi-Agent kostet 3× Zeit und 2× Geld ohne nachgewiesenen Qualitätsgewinn (Westermo). Erst messen, dann aufteilen.
4. **Evidenz ist das Produkt.** Praktiker wollen inspizierbare Belege und nächste Schritte, keine Konfidenzzahl und keine Reasoning-Prosa.
5. **Hypothesen werden getestet, nicht behauptet.** Twin-Simulation vor der Maßnahme (Prozessanlagen-Paper), unterscheidende Tests statt bestätigender (CoffeeBench). Simulation ersetzt keinen echten Test – das muss sichtbar bleiben.
6. **Qualität wird auf einem Szenario-Benchmark gemessen**, mit bekannter Wahrheit, Lösbarkeitsfilter, Wiederholungen (Konsistenz) und Baselines – nicht mit „sieht gut aus".

## 4. Was wir ausdrücklich *nicht* übernehmen

- Kausale Entdeckung (PC-Algorithmus etc., CausalPulse): für 3 Stationen und 7 Messgrößen überdimensioniert; unsere Kausalität steckt in Spezifikation und FMEA.
- Feinjustierung kleiner Modelle (Sensor-Level, KG-HiL): nicht die Aufgabe eines Copilots mit Dokumentenzugriff; außerhalb des Zeitrahmens.
- Asset Administration Shell vollständig: zu schwer; nur die Idee „maschinenlesbare Spezifikation mit Revision".
- Fünf Agenten: siehe These 3.
