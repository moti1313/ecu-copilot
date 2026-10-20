# Konzept V2 – Evidence-Driven EOL Investigator

*„Vom Testfehler zur belegten Ingenieursentscheidung"*

Status: Entwurf zur Abstimmung (16.10.2026). Dieses Dokument und `ARCHITECTURE.md` sind der **Vertrag** für die Implementierung: Was nicht hier steht, wird nicht gebaut; was hier steht, hat ein Abnahmekriterium.

---

## 1. Problem, Lösung und erwarteter Nutzen

1. **Was ist das Problem?** Eine EOL-Prüfung meldet eine Auffälligkeit. Der Fehlercode allein erklärt nicht, ob das Gerät, die Prüfbedingungen, die Messtechnik oder mehrere Ursachen verantwortlich sind. Der Prüfingenieur braucht dafür Prüfdaten und die passende technische Vorgabe.
2. **Warum ist das ein Problem?** Informationen zusammenzutragen und einzuordnen kann Zeit kosten. Eine falsche Zuordnung kann unnötige Nachprüfungen auslösen oder einen Defekt verdecken. Eine ungültige Prüfung lässt den Bauteilzustand offen.
3. **Was ist die Lösung?** Der Copilot führt Daten und Dokumente für eine Untersuchung zusammen, nutzt Analysewerkzeuge und erstellt Bewertungen mit Belegen und vorgeschlagenen Gegenprüfungen. Der Verifier markiert unbelegte oder widersprüchliche Festlegungen. Der Ingenieur beurteilt den Bericht und hält den nächsten Schritt fest. Der Prototyp arbeitet mit synthetischen Daten aus dem Simulator.
4. **Warum diese Lösung?** Explizite Berechnungen und Prüfkriterien liegen in Werkzeugen; das Modell wählt Werkzeuge aus und erklärt die Ergebnisse. Der Vergleich mit dem Regelwerk prüft, ob der Agent zusätzlichen Nutzen bringt. Lauf 4 zeigt bei den untersuchten bekannten Fehlerbildern einen Vorteil des Regelwerks (12/12 gegenüber 8/12 exakt), keinen diagnostischen Vorteil des Agenten. Details: [RUN4_REVIEW.md](RUN4_REVIEW.md).

**Wirtschaftliche Arbeitshypothese:** Der Copilot verkürzt die Vorbereitung und Dokumentation einer Untersuchung bei mindestens gleicher Entscheidungsqualität. Die öffentliche Meldung eines Zulieferers zur Akustikprüfung und die Westermo-Studie motivieren den Anwendungsfall (Quellen in [RESEARCH.md](RESEARCH.md)); der konkrete Arbeitsablauf, Bedarf und Nutzen bei einem konkreten Unternehmen sind damit nicht belegt.

**Spätere Nutzenprüfung:** Prüfingenieure bearbeiten vergleichbare historische Fälle mit ihren bisherigen Werkzeugen und mit dem Copilot. Erfasst werden die gesamte Bearbeitungszeit einschließlich Kontrolle und Dokumentation bis zur fachlich vertretbaren nächsten Maßnahme sowie Fehlentscheidungen und unnötige Gegenprüfungen. Die fachliche Bewertung der nächsten Maßnahme erfolgt durch Prüfexperten. Für die Wirtschaftlichkeit zählen außerdem Integration, Betrieb und Dokumentpflege; freigewordene Zeit ist zunächst zusätzliche Kapazität. Der Szenario-Benchmark beantwortet diese Nutzenfrage nicht.

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

**Methodik (korrigiert nach Review von Lauf 1, 16.10.):** Je Szenario wird nach der Wartezeit **ein Schnappschuss** des Twins genommen (feste Bezugszeit); alle Systeme und Wiederholungen laufen auf denselben Daten. Drei Quoten werden getrennt ausgewiesen: **Abschluss** (auswertbarer Report ohne Fehler), **Diagnose-Konsistenz** (Mehrheitsanteil nur über abgeschlossene Läufe – abgebrochene Antworten zählen nie als Übereinstimmung) und **Korrektheit** (gegen die Wahrheit). Fehlgeschlagene Läufe bleiben in `RESULTS.md` als fehlgeschlagen unter ihrer Konfiguration stehen.

**Systeme im Vergleich**
- **V1S – V1-Werkzeuge mit V2-Schema:** trennt den Effekt der Ingenieur-Werkzeuge vom Effekt des Berichtsformats (Lauf 1 zeigte: V1 erkannte beide Ursachen von S08 im Text, konnte es im alten Befundfeld nur nicht ausdrücken).
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
| **1.5 – Live-Prüfliste (Review 16.10., Vorarbeit für Phase 2)** | Je Station eine Karte „zuletzt geprüfte Einheit" (Serial, Variante, Los, Verdict, Code, Messwert vs. Grenzwert) – ehrlich: keine simulierten Prüfschritte, keine animierte Fortschrittsanzeige; Liste der letzten Prüfungen (SSE); Klick öffnet die Prüfung mit Messwerten und Spezifikationsabschnitt; Belege des Agenten verweisen auf konkrete Prüfungen/Serials. **Drei beschriftete Zonen:** *Demo-Störung (Betreiberwissen, für den Agenten unsichtbar – er hat kein Werkzeug für `/faults`)* · *Beobachtete Prüfungen (Twin-Messung)* · *Hypothese des Copilots*. **Diagnose-Status dreistufig:** „mögliche Ursache" → „durch Evidenz gestützt" → „durch Wiederholungsprüfung bestätigt – im Umfang: n Einheiten, Bedingung X" (dritte Stufe erst mit Phase 2; nie pauschal „ECU gesund"). | Zonen und Prüfliste im UI; Klickpfad Fehler → Prüfung → Spezifikation → Untersuchung funktioniert; Test, dass kein Agenten-Werkzeug `/faults` liest | ½ Tag |
| **2 – Hypothesentest** | Twin mit **persistentem Einheit-Zustand** (Serial → latenter Defekt, individueller Offset); `simulate_retest` (Modellpfad) und `POST /retest` (Messpfad, dieselben Einheiten) als getrennte Wege; Ergebnis gegen Vorhersage; Protokoll; UI-Integration | S01 Ende-zu-Ende: Vorhersage → Freigabe → Re-Test → „gestützt"; **S08: Re-Test nach Abkühlung lässt die Los-Einheiten weiterhin durchfallen** (Defekt persistiert); Szenario S05 unterscheidet Sensorfehler | 2 Tage |
| **3 – Versionen & Robustheit** | vollständige Dokument-Revisionen im RAG (superseded-Dokumente im Index, Filter); Szenarien S06, S07, S09, S10, S16–S20; Latenz-Analyse aus Jaeger, Effort/Modell-Vergleich | S10 besteht; Benchmark auf 20 Szenarien; Latenz-Tabelle (Modell × Effort) | 1–2 Tage |
| **4 – Demo-Fluss** | Leitstand-Sicht (B) und Akte (C) als Einstieg/Ausstieg; Drehbuch | 5-Minuten-Demo läuft zweimal ohne Eingriff | 1–2 Tage |

Reihenfolge ist fix: **erst messen (1), dann testen (2), dann schön (4).**

## 8. Entscheidungen vom 16.10.2026
- **Phase 0 starten**, danach **S01 und S08 vollständig und reproduzierbar** (Phase-1-Durchstich), erst dann der Rest.
- **Jev zurückgestellt.** Bleibt als Option in `ARCHITECTURE.md` §4.4 beschrieben, wird vor Abschluss von Phase 2 nicht gebaut.
- Die vier Punkte aus Review 2 (strukturierte Belegzuordnung, getrennte Bewertung von Prüfgültigkeit und Bauteilfehler, faire Baselines mit Bezugsgrößen, Re-Test derselben Einheiten mit erhaltenen Defekten) sind in §5 (Metriken) und §7 (Abnahme Phase 1/2) und in `ARCHITECTURE.md` §3/§4 festgehalten.

## 10. Vorab festgelegter nächster Benchmark (Lauf 4) – Stand 16.10.2026, abends

Festgelegt **vor** dem Lauf; Änderungen danach werden als solche dokumentiert.

| Punkt | Festlegung |
|---|---|
| Szenarien | **S01** Temperaturdrift (150 s) · **S04** kein Fehler, Frage behauptet Anstieg (60 s; Wahrheit: Zurückhalten) · **S05** T1-Sensor-Offset +9 K (150 s; Wahrheit: `sensor_t1`, Gültigkeit unbekannt, Zurückhalten) · **S08** Drift + Los *regulär* (300 s, Los-Rate 0,15, Lösbarkeit ≥ 8 E-204 und ≥ 8 Los-Fehler) · **S08w** Schwachsignal (150 s, Los-Rate 0,25) – **separat ausgewiesen, nicht in der Gesamtquote** |
| Lösbarkeit | je Szenario vorab definiert (`solvability`); nicht erfüllt ⇒ Szenario gilt als explorativ und wird aus der Gesamtquote herausgenommen, nicht nachträglich umdefiniert |
| Systeme | B0 (mit getrennter Gültigkeits-/Ursachenbewertung), B1, V1S, V2. V1 entfällt (Formateffekt ist mit V1S isoliert; V1 bleibt per `AGENT_PROFILE=v1` reproduzierbar) |
| Wiederholungen | 3 je System und Szenario; eingefrorener Datenstand je Szenario; Twin-Reset mit festem Seed (1000 + Index) |
| Modell / Konfiguration | gpt-5, effort medium, max_tokens 24 000, Prompt 2026-10-16.3 (Regel 13 als Versuch – Wirkung wird an S01 „exakt" abgelesen) |
| Primärmetriken | Bewertungen **exakt** (gefunden ∧ keine Zusatzbehauptung), Befund korrekt, **Zurückhaltung ok** (S04/S05), Herkunft live/Dok |
| Sekundär | Pflicht-Werkzeuge, Nächster Test, Diagnose-Konsistenz (nur abgeschlossene), Latenz, Kosten; Stützung Dok nur informativ |
| **Funktionskriterium** (kein Qualitätsverlust gegenüber dem Regelwerk) | V2 ≥ B0 auf S04/S05 bei „exakt" **und** V2 ohne Zusatzbehauptung auf S01 ≥ 2/3. Trifft das nicht zu, wird das so festgehalten. **Das ist kein Nachweis „Agent lohnt sich"** – zusätzlicher Nutzen (Erklärung, Belege, Testvorschlag, Fälle außerhalb des Regelsatzes) wird separat und qualitativ beurteilt. |
| Korrekturen nach Probelauf (16.10., spät) | B0 bekommt den Untersuchungsbezug aus dem expliziten Szenariofeld `scope` (unabhängig von der Störungsinjektion); S05 Wartezeit 240 s, Temperaturkriterium auf den letzten 3 Minuten; S04-Lösbarkeit prüft nur Datenmenge und Normalrate – ein Fehlalarm von `detect_change` auf der unveränderten Linie wird als **Ergebnis** protokolliert, nicht als Ausschlussgrund; explorative Läufe (S08w, nicht erfüllte Lösbarkeit) werden in Zusammenfassung und Rescoring getrennt ausgewiesen. Lauf 4 startet erst nach einem erneut bestandenen kostenlosen Probelauf (nur B0). |
| Korrekturrunde 2 (Probelauf 20:36 UTC) | Probelauf bestand die Voraussetzungen aller vier regulären Szenarien; S08w sauber explorativ; Archiv vollständig. Zwei Werkzeugkorrekturen, die B0 **und** V2 gleich betreffen: (a) `detect_change` meldete auf der unveränderten Linie (S04, 1,9 %) „signifikant" – Skalierung über den Standardfehler der Vorher-Buckets war bei kleinen Buckets zu klein. Jetzt Zwei-Anteile-z auf Zählwerten plus Mindesteffekt (+1,5 Prozentpunkte und +50 %) für Ausfallraten, gepoolte Streuung plus 1 sd Mindesteffekt für Messgrößen; Fehlalarmtest über 30 Seeds (≤ 1 Alarm). (b) B0s Sensorregel zitierte kein Dokument – ergänzt um DS-MCU-XM32F7 §7.3 und TS-DCU-EOL §4.2 (gleiche Belegpflicht wie der Agent). Probelauf wird wiederholt; Lauf 4 erst danach. |
| Archiv | vollständig (Schnappschuss, Werkzeugausgaben, Commit, Prompt-Version) – ab diesem Lauf vorhanden |
| Kosten/Dauer (Schätzung) | ≈ 45 Modellläufe ≈ 5 $, ≈ 60 min |

## 9. Noch offene Entscheidungen (blockieren Phase 0/1 nicht)
1. Modell für den Benchmark: gpt-5 (teurer, 60 Läufe ≈ 4 $) oder gpt-5-mini (≈ 1 $, evtl. schlechter)? Vorschlag: beide, das ist selbst ein Ergebnis.
2. Judge: gpt-5-mini (gleiche Familie) oder – bei verfügbarem unabhängigem Modellzugang – claude-haiku als unabhängiger Judge? Vorschlag: Haiku, wenn verfügbar.
3. Soll der Twin Firmware-Version und Sensor-Offset als Störungstypen bekommen (für S05/S06)? Vorschlag: ja, es sind ~40 Zeilen.
4. **Jev (TypeSafe) nur als kleines, getrenntes Experiment nach §11** (Vorschlag Reviewer, 17.10.2026): Aufgabe „Welche Gegenprüfung sollte zuerst erfolgen?" mit den Antwortmöglichkeiten *T1 mit Referenzsensor prüfen* / *Los stationsübergreifend untersuchen* / *weitere Daten sammeln* / *keine zusätzliche Untersuchung begründet*. Getrennte Fragen für Sensor- und Bauteilursache, weil beide gleichzeitig vorliegen können. Schattenbetrieb: Jev erhält dieselben Werkzeugausgaben und Spezifikationsauszüge wie das Vergleichssystem; Modellversion (fest), Eingaben, Antwort und Laufzeit werden protokolliert. Bewertung gegen einfache Regeln und V2 mit einer fachlichen Bewertungsregel (wählt es sinnvolle Gegenprüfungen, veranlasst es unnötige Untersuchungen, hält es sich bei unzureichenden Daten zurück); der Schlüsselwortcheck reicht dafür nicht. Vorhandene Fälle zum Entwickeln, zurückgehaltene zum Prüfen. **Zu den Zahlen:** `probabilities` ist die Antwortverteilung des Modells, `confidence` eine daraus berechnete Kennzahl; beides ist ohne eigene Prüfung kein Zuverlässigkeitsnachweis, die Kalibrierung auf unseren ECU-Fällen wird selbst gemessen. Voraussetzung: `TYPESAFE_API_KEY` in `.env` (lokal konfigurieren, nie im Repo). Ein besseres Ergebnis wird erst nach diesem Vergleich behauptet. Jev behebt die S05-Inkonsistenz nicht; deshalb zuerst §11.

## 11. Konsistenzprüfung der Endbewertung – Konzept (Stand 17.10.2026, nach Lauf 4; Review-Korrekturen eingearbeitet)

Noch kein Code, kein Lauf. Dieser Abschnitt legt fest, was ein Verifier-Schritt leisten soll, bevor er gebaut wird.

**Anlass.** S05/V2 0/3 exakt (§10, `RUN4_REVIEW.md` §1). Alle drei Reports enthalten für denselben Geltungsbereich Station 2/B zwei Bewertungen: `invalid_temperature / none_assessable / station_temperature` und `unknown / suspected / sensor_t1`. `derive_finding()` verdichtet INVALID plus `suspected` vertragsgemäß zu `mixed`. Die Herkunftsprüfung (live 155/165) hat das nicht erkannt: Sie löst Referenzen gegen Werkzeugausgaben auf und prüft keine Bewertungen gegeneinander. Fehlende Stufe: Widerspruch zwischen Messpfadvertrauen, Gruppenbewertung und Ursache.

**Erfolgsmaß dieses Schritts.** *Der Verifier macht bestimmte unbelegte oder widersprüchliche Festlegungen nachvollziehbar sichtbar. Die ursprünglichen Reports, Befunde und Exakt-Quoten bleiben unverändert.* Eine verbesserte Diagnoseleistung wird damit nicht behauptet.

**Grundsatz: markieren, nicht verbieten.** Der Verifier setzt keine Ursache ein, ändert keine Bewertung und lässt `derive_finding()` unverändert. Er liefert eine Liste `consistency_flags` neben den bestehenden `flags` in `Verification` (Code, betroffene Bewertung(en), Begründung, fehlender Beleg). UI: Warnmarke je Bewertung. Benchmark: Spalte „Konsistenz-Marken", informativ, nicht Teil von „exakt". Sensorfehler und reale Übertemperatur können gleichzeitig vorliegen, eine Stationsursache schließt einen zusätzlichen Produktdefekt nicht aus; die Marke sagt nur, welche Begründung oder welcher Beleg fehlt.

**Eingaben: ausschließlich das, was im Lauf gespeichert ist.** Report (`assessments`, `evidence`), die tatsächlich ausgeführten Werkzeugaufrufe mit Parametern und Ausgaben, der Dokumentindex. Keine Offline-Nachberechnung aus Snapshots; wenn eine Prüfung im Lauf nicht ausgeführt wurde, lautet die Marke „nicht geprüft", nicht „widersprüchlich". Eine zusätzliche Verifier-Eingabe wäre eine ausdrückliche Erweiterung dieses Abschnitts.

**Grenzen des heutigen Schemas (Review 17.10.).** `assessments` tragen keinen Verweis auf ihre Belege; `evidence[].supports` nennt einen Hypothesentitel als freien Text. Der Verifier kann deshalb „je eigener Beleg je Bewertung" **nicht** zuverlässig zuordnen. Die Marken sind daher im ersten Durchstich **begründete Prüfhinweise**, keine aufhebbaren Bedingungen. Eine explizite Belegzuordnung je Bewertung wäre eine getrennte Schemaänderung mit eigener Festlegung.

**Regeln (deterministisch).** Geltungsbereich = Tupel (station, variant, lot) **und** Zeitfenster der referenzierten Werkzeugaufrufe. Verschiedene Geltungsbereiche sind nicht automatisch unabhängig: „Station 2/B, alle Lose" umfasst das einzelne Los; zwei Referenzen auf denselben T1-Messpfad sind keine unabhängige Temperaturbestätigung.

| Code | Bedingung | Marke (Text) | Art |
|---|---|---|---|
| **K0** Sensorplausibilität nicht geprüft | Bewertung mit `test_validity = invalid_temperature`, und im Lauf wurde `describe_signal` für diesen Geltungsbereich **nicht** erfolgreich ausgeführt | „Temperaturursache festgelegt, Sensorplausibilität (Iq↔T1) nicht geprüft" | Abdeckung |
| **K1** Temperaturmessung selbst in Zweifel | `test_validity = invalid_temperature`, und für denselben Geltungsbereich liegt eine Bewertung mit `root_cause = sensor_t1` **oder** eine gespeicherte `describe_signal`-Ausgabe mit `iq_t1_relation = decoupled` vor | „Temperaturmessung dieses Messpfads in Zweifel; reale Übertemperatur nicht unabhängig belegt" | Widerspruch |
| **K2** Stationsursache mit Bauteilverdacht | `root_cause` ∈ {station_temperature, cell_noise, fixture, sensor_t1} **und** `defect_indication` ∈ {suspected, strong} in derselben Bewertung | „Gemeinsame Festlegung von Stationsursache und Bauteilverdacht benötigt getrennte Begründung" | Prüfhinweis |
| **K3** Konkurrierende Festlegungen im gleichen Geltungsbereich | zwei Bewertungen mit gleichem oder ineinander enthaltenem Geltungsbereich und überlappendem Zeitfenster, eine `invalid_*`, die andere `suspected`/`strong` | „Gemeinsame Festlegung benötigt getrennte Begründung; kann ein berechtigter Mehrfachfehler sein" | Prüfhinweis |
| **K4** Stationsübergreifender Vergleich fehlt | `root_cause = connector_lot` mit `suspected`/`strong`, und kein **erfolgreicher** `cluster_failures`-Aufruf ohne Stationsfilter, der zu Fehlercode, Los, Variante und Zeitbereich der Bewertung passt | „Stationsübergreifender Vergleich für dieses Los fehlt" | Abdeckung |

K4 ist keine Widerspruchsmarke, sondern eine Abdeckungsmarke; ein beliebiger ungefilterter Aufruf genügt nicht. Offen: Einordnung von `firmware` (Station oder Produkt) für K2.

**Nicht-Ziele.** Keine automatische Korrektur. Keine Prompt-Änderung im selben Versuch, sonst ist die Wirkung nicht trennbar. B0 durchläuft dieselbe Prüfung.

**Bewertung in zwei getrennt benannten Schritten.**

1. *Archiv-Replay (Entwicklungsfälle, offline, ohne Modellaufruf)* gegen `data/evals/bench-20261017-090812/`. Erwartung je Lauf:
   - S05/V2 r0–r2: K1 und K3 (3/3); K0 nicht (describe_signal wurde ausgeführt).
   - S05/V1S r0–r2: **K0** („Sensorplausibilität nicht geprüft"); K1 kann dort nicht auslösen – keine der drei Antworten nennt `sensor_t1`, keine ruft `describe_signal` auf (am 17.10. am Archiv geprüft).
   - S08/V2 r0, r2: keine K1–K3; S08/V2 r1: zusätzlich K4.
   - S01, S04 bei V2 und alle B0-Läufe: keine Marke.
2. *Fachliche Prüfung (zurückgehaltene Gegenbeispiele, neu zu bauen, synthetisch, ohne Modellaufruf)*: Sensorfehler **mit** echter Übertemperatur; ungültige Prüfbedingungen **mit** unabhängig belegtem Bauteildefekt; Belege aus unpassenden Zeitfenstern; ineinander enthaltene Geltungsbereiche. Erwartung: K2/K3 erscheinen als Prüfhinweis mit dem vorsichtigen Text, keine Marke behauptet einen Fehler. „B0 bekommt keine Marken" genügt allein nicht als Fehlalarmprüfung.

Dazu Unit-Tests mit synthetischen Reports und ein Replay-Test gegen das Archiv. Erst danach wird getrennt entschieden, ob ein neuer bezahlter Lauf nötig ist; der bekäme eine eigene Festlegung wie §10 und wird nicht aus diesem Abschnitt abgeleitet.

**Sprachregelung.** „Prüfung ungültig" heißt „Bauteilzustand offen, Wiederholung nötig", nie „Bauteil in Ordnung". Der Agent „schlägt Gegenprüfungen vor". Marken sagen „benötigt getrennte Begründung" oder „nicht geprüft", nicht „falsch".

**Replay-Befund (17.10.2026, abends; `evals/consistency_replay.py` gegen `bench-20261017-090812`, 60 Läufe, offline).** Die Erwartungen oben wurden vor dem Replay geschrieben; Abweichungen werden hier festgehalten, die Regeln wurden nicht nachträglich angepasst, damit sie passen.
- Bestätigt: S05/V2 r0–r2 tragen K1 und K3; S05/V1S r0–r2 tragen K0; S01, S04 bei B0 und V2 sowie alle B0-Läufe tragen keine Marke; B1 (kein `assessments`-Feld) trägt nichts.
- Abweichung 1: S05/V2 trägt zusätzlich **K2**, weil die zweite Bewertung `sensor_t1` (Stationsursache) mit `suspected` (Bauteilverdacht) verbindet. Das ist regelkonform und inhaltlich genau der in `RUN4_REVIEW.md` §1 beschriebene Fehler; die Erwartung oben war unvollständig.
- Abweichung 2: **K4 trifft alle drei S08/V2-Wiederholungen**, nicht nur r1. Keine der drei hat `cluster_failures` ohne Stationsfilter aufgerufen; r0 und r2 kamen auf `strong`, weil ihre Abfrage ohne Fehlercode 14 Fälle sah. B0 (stationsübergreifend, E-120) und der explorative S08w/V2 r2 (stationsübergreifender Aufruf vorhanden) tragen keine K4. Die Marke beschreibt Abdeckung, nicht Richtigkeit: die Bewertung von r0/r2 war „exakt", der stationsübergreifende Vergleich fehlte trotzdem.
- Zusätzlich sichtbar: V1S trägt K0 auf S01, S05, S08, S08w (kein `describe_signal` im V1-Werkzeugsatz) und K4 auf allen S08-Läufen (kein `cluster_failures`); S08/V1S r2 trägt K3 (Losursache ohne Los im Geltungsbereich, identisches Tupel mit der INVALID-Zeile).
- Umsetzung des ersten Durchstichs: K3 löst nur bei identischem Tupel (station, variant, lot) aus. Verschachtelte Geltungsbereiche und Zeitfenster werden nicht verglichen (Grenze, siehe oben), sonst träfe K3 jeden berechtigten Mehrfachfehler (alle S08-Läufe von B0 und V2). K4 verlangt einen erfolgreichen `cluster_failures`-Aufruf ohne Stationsfilter mit `by=lot`, passender Variante (oder alle), für alle Fehlercodes oder einen im Report genannten Code, der das bewertete Los in `groups` oder `top` ausweist (Review Reviewer 17.10.: ein Vergleich zu einem fremden Code hebt die Marke nicht auf, ein Los auf Platz 2 der Gruppen genügt). K0 verlangt `tested > 0` und einen stationsbezogenen Geltungsbereich; K1 läuft unabhängig von K0 (Vergleich der Bewertungen untereinander auch ohne Signalaufruf).
- Reports, Befunde und Exakt-Quoten sind unverändert (`test_consistency.py` prüft, dass `derive_finding()` für das S05-Muster weiterhin `mixed` liefert).

## 12. Vorab-Festlegung: Jev-Schattenexperiment (Stand 17.10.2026, abends; noch kein Aufruf ausgeführt)

Festgelegt **vor** dem ersten Aufruf; Änderungen danach werden als solche dokumentiert. Grundlage: §9 Punkt 4, Vorschlag des Reviewer, TypeSafe-Dokumentation (gelesen 17.10.2026: `docs.typesafe.ai` Quickstart, Choice, Confidence, Models, API).

| Punkt | Festlegung |
|---|---|
| Frage, die das Experiment beantwortet | Wählt ein System-One-Modell aus **denselben Werkzeugausgaben** wie V2 eine fachlich sinnvolle **nächste Gegenprüfung** und trennt es Sensor- von Bauteilverdacht, ohne selbst Text zu erzeugen? Es ersetzt weder Untersuchung noch Belege noch Report. |
| Modell | `jev-1.13.0`, **exakt gepinnt** (Alias `jev-latest` zeigt am 17.10.2026 auf diese Version, wandert aber bei neuen Releases; versionierte IDs werden im Feld `model` akzeptiert). Endpunkt `POST https://api.typesafe.ai/v1/systemone`, Bearer-Schlüssel aus `TYPESAFE_API_KEY` (nur `.env`). Aufruf im Backend über `httpx` (bereits Abhängigkeit); das Paket `typesafe-sdk` ist eine gleichwertige Alternative, bringt hier aber keine zusätzliche Funktion. |
| Zustand (State) | **Aufbereitete Evidenz aus dem gespeicherten Lauf, nicht byte-gleich mit dem, was V2 sah** (Review 17.10.): (a) Ingenieurfrage; (b) Ausgaben der Ingenieurwerkzeuge `get_station_stats`, `check_validity`, `detect_change`, `describe_signal`, `cluster_failures` vollständig mit Eingaben; (c) **weggelassen:** Einzelergebnislisten (`get_recent_results` u. ä.), durch die V2 blättern konnte; (d) `search_docs`-Treffer **gekürzt** auf Zitat + 600 Zeichen; (e) **ergänzt:** Spezifikationsauszug (Grenzwerte, Gültigkeitsfenster) explizit, den V2 über Spezifikations-JSON und Dokumente hatte; (f) **nicht** enthalten: Report, Hypothesen, Bewertungen oder Antworttext von V2 (Schattenbetrieb, keine Rückkopplung). „Dieselbe Evidenz" heißt also: dieselben Werkzeugergebnisse, anders verpackt; der Vergleich wird so gelesen. Umfang 2,7k bis 6,9k Token je Lauf, unter der Grenze von 32k je Frage / 64k je Anfrage. |
| Fragen (drei, getrennt) | **Q1 `next_check` (Choice):** „Welche Gegenprüfung sollte zuerst erfolgen?" mit fünf Optionen: `reference_thermometer` (T1 der Station mit unabhängigem Referenzfühler vergleichen) · `retest_valid_temperature` (betroffene Einheiten unter gültigem Temperaturfenster wiederholen) · `lot_cross_station` (Los stationsübergreifend untersuchen) · `collect_more_data` (weitere Daten sammeln) · `no_additional_check` (keine zusätzliche Untersuchung begründet). **Q2 `t1_unreliable` (Noul):** „Der Temperaturmesspfad T1 dieser Station ist unzuverlässig." **Q3 `product_defect` (Noul):** „Über die normale Hintergrund-Ausfallrate (einzelne Einheiten mit gemischten Codes) hinaus zeigen die Daten eine **zusätzliche systematische** Produktfehlerursache für die untersuchte Gruppe, unabhängig von der Prüfumgebung (z. B. Konzentration in einem Los, einer Firmware, einem Bauteil)." (Review 17.10.: enger gefasst, damit S04 mit normalen Einzelfehlern eindeutig „nein" erwartet) Sensor- und Bauteilfrage sind getrennt, weil beides gleichzeitig vorliegen kann. |
| Vorab erwartete Antworten (Entwicklungsfälle Lauf 4) | S01: Q1 `retest_valid_temperature`, Q2 nein, Q3 nein · S04: Q1 `no_additional_check`, Q2 nein, Q3 nein · S05: Q1 `reference_thermometer`, Q2 **ja**, Q3 nein · S08/S08w: Q1 `lot_cross_station` **oder** `retest_valid_temperature` (beide vertretbar; ausgewiesen wird, welche), Q2 nein, Q3 **ja**. Noul-Schwelle: ja ≥ 0,7, nein ≤ 0,3, dazwischen „unentschieden" (zählt weder als Treffer noch als Fehler, wird gezählt). |
| Vergleich | Gegen (a) die Vorab-Erwartung, (b) V2s `next_test` desselben Laufs (Schlüsselwortprüfung, bekannt grob), (c) eine feste Regel (B0-Logik: decoupled → Referenzfühler; Los konzentriert → Los stationsübergreifend; invalid_temperature → Wiederholung; sonst keine). Ergebnis: Trefferquote je Frage und Szenario, Anteil „unentschieden", Anteil unnötiger Untersuchungen (Q1 ≠ `no_additional_check` auf S04). |
| Zahlen | `probabilities` ist die Antwortverteilung; `confidence` ist daraus berechnet: für Choice (p_max − 1/n)/(1 − 1/n), für Noul ohne eigenes Feld. Beides ist **kein** Zuverlässigkeitsnachweis. Kalibrierung wird selbst gemessen: je Konfidenzband Trefferquote gegen die Erwartung; mit 15 Fällen nur als Hinweis, nicht als Aussage. |
| Entwicklungs- vs. Prüffälle | Entwicklung: die 15 V2-Läufe aus Lauf 4 (fünf Szenarien × 3). Prüfung: **zurückgehaltene** synthetische Fälle (neue Snapshots, nicht vor der Festlegung angesehen): Sensorfehler **mit** echter Übertemperatur; ungültige Prüfbedingungen **mit** unabhängig belegtem Bauteildefekt; unauffällige Linie mit anderer Frageformulierung. Erst nach der Entwicklungsrunde erzeugt. |
| Protokoll | `data/evals/jev/jev-<zeitstempel>.jsonl`, je Zeile: Lauf-Schlüssel, **der exakte gesendete Request (Zustand, Modell, Fragen)**, angefordertes und zurückgemeldetes Modell, SHA-256 des Zustands, Antworten (choice, probabilities, confidence / noul), Token, Latenz, Request-ID, **Codeversion (Git-Commit, dirty-Flag)**. Review 17.10.: ein Hash allein rekonstruiert keine Eingabe; die Daten sind synthetisch, der Zustand darf im Protokoll stehen. |
| Kosten/Dauer | 0,042 $ je Million Eingabetoken, Ausgabe kostenlos: 15 Anfragen × ≈ 7k Token ≈ **0,005 $**. Trotzdem gilt: Aufruf erst nach ausdrücklicher Freigabe durch den Betreiber, `--send` im Skript, Schlüssel nur in `.env`. |
| Erfolgsmaß | „Jev wählt auf den Entwicklungsfällen in ≥ 12/15 die erwartete Gegenprüfung und trennt Q2/Q3 in ≥ 12/15 korrekt" wäre ein **Hinweis**, dass ein typisiertes Auswahlmodell für diese Teilaufgabe taugt. Es bleibt kein Nachweis für Produktionsnutzen und ändert nichts am Ergebnis von Lauf 4 oder an §11. Verfehlt Jev die Erwartung, wird das ebenso festgehalten. |
| Nicht-Ziele | Kein Einbau in den Antwortpfad, keine automatische Freigabe, kein Ersatz des Verifiers, keine Text- oder Belegerzeugung durch Jev. |

**Ergebnis (17.10.2026, 21:17 UTC, nach Freigabe):** 15 Anfragen, 0,006 USD. Q1 12/15 (S01 0/3: Referenzfühler statt Wiederholung bei echter Drift; S08/S08w: Wiederholung statt Losvergleich, zulässig), Q2 15/15, Q3 15/15, 0 unentschieden. Erfolgsmaß erreicht, Q1 genau an der Schwelle: ein Hinweis, kein Nachweis. Die feste Regel (c) trifft 15/15. Einzelheiten und Grenzen: `RESULTS.md`, Abschnitt Jev-Schattenexperiment. Nächster Schritt nach §12 wären die zurückgehaltenen Prüffälle; nicht gestartet.

**Umsetzung ohne Aufruf (17.10.2026):** `copilot/jev.py` (Zustandsaufbau, Fragen, HTTP-Client mit austauschbarem Transport, Protokoll, Erwartungstabelle), `tests/test_jev.py` (Attrappe über `httpx.MockTransport`, kein Netz, kein Schlüssel), `evals/jev_shadow.py` (Standard `--dry-run`: baut Zustände und zeigt Größen; sendet nur mit `--send`).

## 13. Ausblick: einmalige gezielte Überarbeitung aus den Konsistenz-Marken (Konzept, Stand 17.10.2026; nicht gestartet)

Kein Code, kein Lauf. Dieser Abschnitt beschreibt den nächsten Versuch, damit er in der Präsentation benannt werden kann, ohne eine Wirkung zu behaupten.

**Ablauf.** Antwort → Konsistenzprüfung (§11) → bei Marke **eine** gezielte Überarbeitung → erneute Prüfung → beide Fassungen gespeichert. Die Rückmeldung an das Modell wird **aus den Marken erzeugt**, nicht frei formuliert (z. B. K1: „Du stellst Übertemperatur fest und bezweifelst zugleich den Temperatursensor. Prüfe, welche Festlegung belegt ist; trenne alternative Erklärungen von gleichzeitig belegten Ursachen." · K4: „Die Losbewertung stützt sich nur auf Station 2; der stationsübergreifende Vergleich fehlt."). Das ist gezielte Kritik aus einer deterministischen Quelle, keine allgemeine Selbstkritik.

**Präzisierungen (Review 17.10.).**
1. **S05 braucht mehr als Umformulieren.** Die Überarbeitung muss die strukturierten Felder `assessments` ändern dürfen und wird daran gemessen. Eine vorsichtigere Erklärung bei unverändert widersprüchlichen Bewertungen gilt als **nicht behoben**. Die tatsächliche Temperatur bleibt bis zu einer unabhängigen Messung offen; die richtige Überarbeitung ist `unknown / none / sensor_t1`, nicht eine neue Festlegung.
2. **Zusätzliche Werkzeugaufrufe nur auf dem eingefrorenen Datenstand.** Für K4 muss der Agent `cluster_failures` stationsübergreifend nachholen können; diese Aufrufe laufen gegen den archivierten Snapshot desselben Laufs, nie gegen den laufenden Twin. Sonst wäre eine bessere zweite Antwort durch neue Messdaten erklärbar und der Effekt der Überarbeitung nicht trennbar.
3. **Der kleine Vorversuch ist ein archivbasierter Modellversuch mit bezahlten Aufrufen.** Er braucht keinen Twin, aber Festlegung und Freigabe. Die drei S05/V2-Fehlerberichte zeigen nur, ob die Schleife den bekannten Fehler behebt; ob sie **richtige Antworten verschlechtert**, zeigen erst ursprünglich korrekte Fälle (S01/V2, S04/V2, S08/B0-ähnliche Reports mit berechtigtem Mehrfachfehler, der K3-Hinweise tragen darf).

**Präzisierungen 2 (Review 17.10., spät).**
- **Trigger ausdrücklich:** Im ersten Versuch löst **nur K1** eine Überarbeitung aus (Widerspruch). K0 und K4 melden fehlende Untersuchungsabdeckung und werden später getrennt behandelt (Nachholen eines Aufrufs, kein Umschreiben); K2 und K3 können bei berechtigten Mehrfachfehlern erscheinen und lösen **keine** Überarbeitung aus.
- **Werkzeugzugriff mit Datenstand und Historie:** Die Überarbeitung darf benötigte Analysewerkzeuge nachholen, arbeitet dabei auf demselben eingefrorenen Snapshot und **behält die vollständige Referenzhistorie** (die Werkzeugaufrufe 1…n der ersten Antwort bleiben nummeriert erhalten, neue Aufrufe werden angehängt). Sonst verfälschen neue Daten oder verschobene Belegnummern (`evidence[].ref.tool_call`) die Herkunftsprüfung und den Vergleich.
- **Budget je Überarbeitung:** höchstens 3 zusätzliche Werkzeugaufrufe, höchstens ein Modellaufruf mit demselben `max_tokens` wie Lauf 4, Laufzeitgrenze 240 s; Überschreitung wird als „Überarbeitung abgebrochen" gewertet und protokolliert. „Höchstens einmal" begrenzt allein den Aufwand nicht.
- **Fehlalarm fachlich definiert:** Eine richtige Diagnose kann unzureichend belegt sein und zu Recht eine Marke tragen. „Bewertung exakt, trotzdem Marke" zählt **nicht** automatisch als Fehlalarm; Fehlalarm ist nur eine Marke, deren Bedingung nachweislich nicht erfüllt ist (Regelfehler), geprüft durch Lesen des Falls.

**Metriken, getrennt ausgewiesen (vorhandene Namen aus `evals/bench.py`):** `assessments_exact` und `finding_ok` jeweils **vor und nach** der Überarbeitung · Fehler behoben (vorher nicht exakt, nachher exakt) · **richtige Antwort verschlechtert** (vorher exakt, nachher nicht) · Herkunft live/Dok vor und nach · Marken vor/nach als getrennte Kennzahl, nicht als Erfolgsmaß. „Weniger Marken" allein ist kein Erfolg; berechtigte Mehrfachfehler dürfen weiterhin K3 tragen, „keine Marke" ist kein Beweis für eine richtige Diagnose.

**Stufen.** (a) Konzept (dieser Abschnitt). (b) **Kleinster archivbasierter Vergleich:** die 3 S05/V2-Fehlerberichte (K1) plus ursprünglich korrekte Kontrollfälle (S01/V2 3, S04/V2 3, S08/V2 r0 und r2), bei denen K1 künstlich nicht gesetzt ist und die Überarbeitung trotzdem angeboten wird, um Verschlechterung zu messen. Dieselbe erste Antwort wird einmal unverändert und einmal überarbeitet bewertet; B0 wird nicht neu berechnet. gpt-5 wie Lauf 4, ≈ 11 Modellaufrufe, geschätzt ≈ 0,5 USD; eigene Festlegung wie §10/§12 vor dem ersten Aufruf. (c) Erst bei positivem und nicht verschlechterndem Vorversuch ein Lauf 5 mit der Schleife im Agenten, eigene Festlegung, kostenloser Probelauf, Vergleich gegen Lauf 4 auf denselben Szenarien.

**Nicht-Ziele.** Keine automatische Übernahme der zweiten Antwort ohne Anzeige beider Fassungen. Keine Behauptung einer Verbesserung vor Stufe (c). Nicht vor der Präsentation.

**Satz für die Präsentation.** „Als nächsten Schritt würde ich die deterministischen Hinweise für eine einmalige Überarbeitung nutzen. Dabei messe ich Verbesserungen und Verschlechterungen getrennt. Bisher zeigt mein Prototyp die Widersprüche an; die Wirkung dieser Überarbeitung ist noch offen."
