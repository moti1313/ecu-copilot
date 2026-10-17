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
