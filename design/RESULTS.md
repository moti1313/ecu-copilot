# Benchmark-Ergebnisse

Jeder Abschnitt ist ein Lauf von `evals/bench.py`. Zahlen sind Mittelwerte über Szenarien × Wiederholungen; Details in `data/evals/bench-*.json`.

## 2026-10-16 19:00 UTC · Modell gpt-5 · Szenarien S01-temperature-drift, S08-drift-and-bad-lot · 24 Läufe

| System | Befund | Bewertungen (alle Gruppen) | Ursache | Pflicht-Tools | Zitat vorh. | Herkunft live | Herkunft Dok | Stützung Dok | Nächster Test | Konsistenz | Ø s | Ø $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B0 | 100 % | 100 % | 100 % | 100 % | 100 % | 100 % (18/18) | 100 % (9/9) | 0 % (0/9) | 100 % | 100 % | 0.0 | 0.000 |
| B1 | 17 % | 0 % | 0 % | 0 % | 33 % | 0 % (0/32) | 74 % (17/23) | 13 % (3/23) | 33 % | 67 % | 54.4 | 0.069 |
| V1 | 50 % | 0 % | 0 % | 0 % | 83 % | 0 % (0/30) | 87 % (26/30) | 30 % (9/30) | 50 % | 83 % | 76.7 | 0.111 |
| V2 | 0 % | 0 % | 0 % | 100 % | 0 % | – | – | – | 0 % | 100 % | 84.1 | 0.134 |

Je Szenario (Befund korrekt / Bewertungen korrekt, über Wiederholungen):

| Szenario | B0 | B1 | V1 | V2 |
|---|---|---|---|---|
| S01-temperature-drift | 3/3 · 3/3 | 1/3 · 0/3 | 3/3 · 0/3 | 0/3 · 0/3 |
| S08-drift-and-bad-lot | 3/3 · 3/3 | 0/3 · 0/3 | 0/3 · 0/3 | 0/3 · 0/3 |

Fehler: 7 Läufe – v2/S01-temperature-drift: answer truncated (max_completion_tokens); v2/S01-temperature-drift: answer truncated (max_completion_tokens); v2/S01-temperature-drift: answer truncated (max_completion_tokens); v1/S08-drift-and-bad-lot: answer truncated (max_completion_tokens); v2/S08-drift-and-bad-lot: answer truncated (max_completion_tokens)

> **Anmerkung zu diesem Lauf:** Alle sechs V2-Läufe wurden bei `max_completion_tokens = 8000` abgeschnitten (bei gpt-5 zählen Reasoning-Tokens mit) – die V2-Zeile misst die Konfiguration, nicht das System. Limit auf 24 000 erhöht, V1/V2 im nächsten Abschnitt wiederholt. „Herkunft live" ist für B1/V1 strukturell 0, weil das V1-Schema keine Referenzen hat (ab dem nächsten Lauf als „n/a" ausgewiesen). „Stützung Dok" 0 % bei B0: B0 formuliert seine Belege auf Deutsch, die Dokumente sind Englisch – die Schlüsselwort-Heuristik findet sie nicht; eine bekannte Grenze der Heuristik, kein Befund über B0.

## 2026-10-16 19:24 UTC · Modell gpt-5 · Szenarien S01-temperature-drift, S08-drift-and-bad-lot · 12 Läufe

| System | Befund | Bewertungen (alle Gruppen) | Ursache | Pflicht-Tools | Zitat vorh. | Herkunft live | Herkunft Dok | Stützung Dok | Nächster Test | Konsistenz | Ø s | Ø $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V1 | 50 % | 0 % | 0 % | 0 % | 100 % | – | 67 % (22/33) | 15 % (5/33) | 33 % | 67 % | 69.2 | 0.109 |
| V2 | 83 % | 83 % | 100 % | 100 % | 100 % | 97 % (108/111) | 100 % (30/30) | 40 % (12/30) | 100 % | 83 % | 101.1 | 0.153 |

Je Szenario (Befund korrekt / Bewertungen korrekt, über Wiederholungen):

| Szenario | V1 | V2 |
|---|---|---|
| S01-temperature-drift | 3/3 · 0/3 | 2/3 · 3/3 |
| S08-drift-and-bad-lot | 0/3 · 0/3 | 3/3 · 2/3 |

> **Anmerkung zu diesem Lauf (V1/V2, Limit 24 000):** Noch *ohne* eingefrorenen Datenstand und ohne Twin-Reset – die Systeme liefen nacheinander auf dem lebenden Twin, und die E-120-Fehler des vorigen S08-Laufs (Lauf 1) lagen noch im 30-Minuten-Fenster (Lösbarkeitsprüfung: 144 Los-Fehler statt ~20). Das erklärt vermutlich den einen „mixed"-Befund von V2 auf S01. Beantwortet ist: Die V2-Abbrüche in Lauf 1 waren das Token-Limit. Der nächste Lauf verwendet Schnappschuss + Reset je Szenario und alle fünf Systeme.

> **Nachträgliche Auswertung von Lauf 2 (`evals/rescore.py`, ohne Modellaufrufe):** Zusatzbehauptungen zählen.

| System | Bewertungen gefunden | Zusatz-Behaupt. Ø | Läufe mit Zusatzbehauptung | Bewertungen exakt | Befund korrekt |
|---|---|---|---|---|---|
| V1 | 0 % | 0.00 | 0/6 | 0 % | 50 % |
| V2 | 83 % | 0.17 | 1/6 | 67 % | 83 % |

Zusatzbehauptungen im Detail:
- v2/S01-temperature-drift/r0: {'station': 2, 'variant': 'B', 'lot': None} valid/suspected/unknown

## 2026-10-16 20:05 UTC · Modell gpt-5 · max_tokens 24000 · Szenarien S01-temperature-drift, S08-drift-and-bad-lot · 30 Läufe · eingefrorener Datenstand je Szenario

| System | Abschluss | Befund korrekt | Bewertungen korrekt | Ursache | Zurückhaltung ok | Pflicht-Tools | Zitat vorh. | Herkunft live | Herkunft Dok | Stützung Dok | Nächster Test | Diagnose-Konsistenz | Ø s | Ø $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B0 | 100 % | 50 % | 50 % | 50 % | 100 % | 100 % | 100 % | 100 % (12/12) | 100 % (6/6) | 0 % (0/6) | 100 % | 100 % | 0.0 | 0.000 |
| B1 | 100 % | 0 % | 0 % | 0 % | 50 % | 0 % | 50 % | n/a | 79 % (22/28) | 21 % (6/28) | 83 % | 100 % | 61.7 | 0.071 |
| V1 | 100 % | 50 % | 0 % | 0 % | 100 % | 0 % | 100 % | n/a | 76 % (26/34) | 29 % (10/34) | 100 % | 100 % | 85.6 | 0.112 |
| V1S | 100 % | 100 % | 83 % | 100 % | 100 % | 0 % | 100 % | 93 % (81/87) | 100 % (30/30) | 33 % (10/30) | 67 % | 100 % | 107.5 | 0.146 |
| V2 | 100 % | 83 % | 100 % | 100 % | 100 % | 100 % | 83 % | 96 % (87/91) | 100 % (25/25) | 48 % (12/25) | 83 % | 83 % | 92.3 | 0.121 |

Je Szenario: abgeschlossen / Befund korrekt / Bewertungen korrekt (über Wiederholungen):

| Szenario | B0 | B1 | V1 | V1S | V2 |
|---|---|---|---|---|---|
| S01-temperature-drift | 3 / 3 / 3 von 3 | 3 / 0 / 0 von 3 | 3 / 3 / 0 von 3 | 3 / 3 / 3 von 3 | 3 / 2 / 3 von 3 |
| S08-drift-and-bad-lot | 3 / 0 / 0 von 3 | 3 / 0 / 0 von 3 | 3 / 0 / 0 von 3 | 3 / 3 / 2 von 3 | 3 / 3 / 3 von 3 |

Lesehilfe: *Abschluss* = auswertbarer Report ohne Fehler; *Diagnose-Konsistenz* = Mehrheitsanteil nur über abgeschlossene Läufe; *Zurückhaltung ok* = 'unklar' genau dann, wenn die Wahrheit es verlangt; *Herkunft live* n/a für Systeme ohne Referenzen (V1-Schema). B0 kennt die Szenario-Scope-Angabe (Station/Variante) aus der Szenariodefinition, nicht aus der Frage.

> **Fußnote zu diesem Lauf (Lauf 3, 30 Läufe):** gemeinsamer eingefrorener Datenstand und Twin-Reset je Szenario – aber **noch ohne vollständiges Daten- und Werkzeugarchiv** (der Lauf wurde vor dem Archiv-Patch gestartet; Rohdaten lassen sich nachträglich nicht herstellen). **S08: Lösbarkeitskriterium nicht erfüllt** – nach dem Reset lagen nach 150 s Wartezeit nur 3 E-204-Fails im 10-Minuten-Fenster (Kriterium: ≥ 8), weil die Los-Einheiten bereits in Schritt 1 (LIN, E-120) ausfallen und nicht mehr zur Ruhestrommessung kommen. Die S08-Ergebnisse sind damit ein *Schwachsignal-Fall*: B0s Regel (≥ 5 E-204-Fails) griff nicht; V1S/V2 erkannten die Temperaturseite trotzdem aus 3/3 INVALID-Fails. Für den nächsten Lauf: Wartezeit für S08 auf 300 s oder Los-Rate senken, damit das Kriterium erfüllt ist.

Nachträgliche Auswertung (`evals/rescore.py`):

| System | Bewertungen gefunden | Zusatz-Behaupt. Ø | Läufe mit Zusatzbehauptung | Bewertungen exakt | Befund korrekt |
|---|---|---|---|---|---|
| B0 | 50 % | 0.00 | 0/6 | 50 % | 50 % |
| B1 | 0 % | 0.00 | 0/6 | 0 % | 0 % |
| V1 | 0 % | 0.00 | 0/6 | 0 % | 50 % |
| V1S | 83 % | 0.00 | 0/6 | 83 % | 100 % |
| V2 | 100 % | 0.17 | 1/6 | 83 % | 83 % |

Zusatzbehauptungen im Detail:
- v2/S01-temperature-drift/r1: {'station': 2, 'variant': 'B', 'lot': None} valid/suspected/unknown

### Auswertung von Lauf 3 (16.10.2026, nach Lesen der fehlerhaften Antworten)

**Die drei Vergleiche**

| Vergleich | Was sich ändert | Zahlen (S01+S08, je 3 Läufe) |
|---|---|---|
| **V1 → V1S** (nur Berichtsformat) | Befund 50 % → 100 %; Bewertungen 0 % → 83 % (exakt 83 %, 0 Zusatzbehauptungen); Herkunft live n/a → 93 %; Dokument-Zitate existent 76 % → 100 % | **Das Format bringt den größten Teil des Gewinns.** V1 hatte S08 im Text erkannt, konnte es im Befundfeld nicht ausdrücken; mit Referenzpflicht werden die Zitate exakt. Preis: +25 % Latenz (86 → 108 s), +30 % Kosten (0,11 → 0,15 $). |
| **V1S → V2** (zusätzlich Ingenieur-Werkzeuge) | Bewertungen gefunden 83 % → 100 %, exakt 83 % → 83 % (V2: 1 Zusatzbehauptung in 6); Pflicht-Werkzeuge 0 % → 100 %; Los-Bewertung „strong“ 2/3 → 3/3; Latenz 108 → 92 s; Kosten 0,146 → 0,121 $ | Mit Werkzeugen wurde die erwartete Bewertung in allen Läufen gefunden, und **V2 war in diesem Lauf schneller und günstiger** (weniger Rohdaten im Kontext ist die plausible Ursache – gemessen ist sie nicht). Dreimal „strong“ statt zweimal ist eine **veränderte Einstufung, keine nachgewiesene Kalibrierung.** Überinterpretation verhindern die Werkzeuge nicht (siehe unten). |
| **B0 → V2** (Regelwerk vs. Agent) | S01: erwartete Bewertung gefunden B0 3/3, V2 3/3 – aber **Gesamtbefund und „exakt“: B0 3/3, V2 2/3** (Zusatzbehauptung). S08 (Lösbarkeitskriterium verfehlt, explorativ): B0 1/2, V2 3/3. B0: 0 s, 0 $; V2: 92 s, 0,12 $ | Auf dem regulären Szenario S01 liegt B0 vorn (exakt, ohne Zusatzbehauptung). V2s Vorteil auf S08 ist ein Hinweis aus einem Schwachsignal-Versuch, keine Rangliste; die gemeinsame 50 %-gegen-83 %-Quote ist nicht belastbar. In B0s Schwelle (mindestens 5 E-204-Fails) steckt zudem eine Designfrage – siehe Konsequenz 3. |

**Die fehlerhaften Antworten, gelesen**
- *V2 / S01 / r1 („mixed", Zusatzbehauptung):* Der Agent erklärte E-204 korrekt als ungültig und fügte eine zweite Bewertung „gültig / vermutet / unbekannt" für die **drei verbleibenden Hintergrund-Fails** (2× E-310, 1× E-401) hinzu – also für die normale Grundrate. Überinterpretation des Rauschens. → Prompt-Regel 13 (Grundrate ist keine Bewertung), Prompt-Version 2026-10-16.3. Ob die Regel wirkt, zeigt erst der nächste Lauf.
- *V2 / S08 / r2 („Zitat vorh." = nein):* **Metrikfehler, kein Agentenfehler.** Der Agent zitierte „TS-DCU-EOL 4.2" (ohne §, wie der Prompt es verlangt); die Wahrheit prüfte auf „§4.2". Vergleich normalisiert; die Zeile wäre mit korrekter Metrik bestanden (V2 „Zitat vorh." → 100 %).
- *V1S / S08 / r1 (1/2):* Los-Bewertung „vermutet" statt „stark". Ohne `cluster_failures` sah V1S nur ≤ 40 Rohzeilen und blieb vorsichtig – vertretbar, aber unter dem Kriterium. Genau hier helfen die Werkzeuge (V2: 3/3 „stark").
- *B0 / S08 (1/2):* Temperaturregel verlangt ≥ 5 E-204-Fails; es gab 3 (Lösbarkeit nicht erfüllt). Kein Regelfehler, ein Szenario-Setup-Problem (Los-Einheiten fallen in Schritt 1 aus und erreichen die Ruhestrommessung nicht).

**Was noch nicht aussagekräftig ist:** „Stützung Dok" (Schlüsselwort-Heuristik, 21–48 %), Diagnose-Konsistenz (bei 3 Läufen grob), alles über zwei Szenarien hinaus.

**Konsequenzen (Review 16.10., abends):** (1) Prompt-Regel 13 ist ein Versuch; sie bezieht sich ausdrücklich auf *zusätzliche Erklärungen für den Linienzustand* – einzelne echte Fehlprüfungen bleiben auch innerhalb der Grundrate sichtbar und untersuchbar. Metrik-Normalisierung eingebaut. Kein neuer Zwei-Szenarien-Lauf. (2) S08 wird geteilt: **S08 regulär** (vorab festgelegt: Wartezeit 300 s, Los-Rate 0,15, Lösbarkeit mindestens 8 E-204) und **S08w** als separater Schwachsignal-Versuch (bisherige Bedingungen). (3) **B0: Prüfgültigkeit und Ursache getrennt** – Gültigkeit wird je Messung deterministisch bewertet (keine Mindestanzahl); eine Ursachen-/Häufungsaussage braucht Anzahl, Verlauf und Bezugsgrößen. Sonst entstünde ein scheinbarer Agentenvorteil aus einer unnötigen Einschränkung des Regelwerks. (4) Nächster Benchmark vorab festgelegt (`CONCEPT.md` §10): S01, S04, S05, S08, S08w.

## 2026-10-16 20:36 UTC · Modell gpt-5 · max_tokens 24000 · Szenarien S01-temperature-drift, S04-no-fault, S05-sensor-offset, S08-drift-and-bad-lot, S08w-drift-and-bad-lot-weak · 5 Läufe (4 regulär, 1 explorativ) · eingefrorener Datenstand je Szenario

**Reguläre Szenarien (Lösbarkeit erfüllt, nicht explorativ) – Gesamtquoten** (S01-temperature-drift, S04-no-fault, S05-sensor-offset, S08-drift-and-bad-lot, 4 Läufe)

| System | Abschluss | Befund korrekt | Bewertungen korrekt | Ursache | Zusatz-Behaupt. Ø | Bewertungen exakt | Zurückhaltung ok | Pflicht-Tools | Zitat vorh. | Herkunft live | Herkunft Dok | Stützung Dok | Nächster Test | Diagnose-Konsistenz | Ø s | Ø $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B0 | 100 % | 75 % | 75 % | 75 % | 0.25 | 75 % | 75 % | 75 % | 75 % | 100 % (7/7) | 100 % (3/3) | 0 % (0/3) | 75 % | n/a | 0.0 | 0.000 |

**Explorative Läufe (als explorativ markiert oder Lösbarkeit nicht erfüllt) – separat, nicht in der Gesamtquote** (S08w-drift-and-bad-lot-weak, 1 Läufe)

| System | Abschluss | Befund korrekt | Bewertungen korrekt | Ursache | Zusatz-Behaupt. Ø | Bewertungen exakt | Zurückhaltung ok | Pflicht-Tools | Zitat vorh. | Herkunft live | Herkunft Dok | Stützung Dok | Nächster Test | Diagnose-Konsistenz | Ø s | Ø $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B0 | 100 % | 100 % | 100 % | 100 % | 0.00 | 100 % | 100 % | 100 % | 100 % | 100 % (3/3) | 100 % (2/2) | 0 % (0/2) | 100 % | n/a | 0.0 | 0.000 |

Je Szenario: abgeschlossen / Befund korrekt / Bewertungen exakt (über Wiederholungen); (E) = explorativ:

| Szenario | B0 |
|---|---|
| S01-temperature-drift | 1 / 1 / 1 von 1 |
| S04-no-fault · Detektor-Fehlalarm auf unveränderter Linie: ja | 1 / 0 / 0 von 1 |
| S05-sensor-offset | 1 / 1 / 1 von 1 |
| S08-drift-and-bad-lot | 1 / 1 / 1 von 1 |
| S08w-drift-and-bad-lot-weak (E) | 1 / 1 / 1 von 1 |

Lesehilfe: *regulär* = Lösbarkeit erfüllt und nicht explorativ; nur diese Läufe bilden die Gesamtquoten. *Abschluss* = auswertbarer Report ohne Fehler; *Diagnose-Konsistenz* = Mehrheitsanteil nur über abgeschlossene Läufe; *Zurückhaltung ok* = 'unklar' genau dann, wenn die Wahrheit es verlangt; *Herkunft live* n/a für Systeme ohne Referenzen (V1-Schema). *Herkunft* heißt: Die automatische Prüfung konnte die angegebene Quelle bzw. den referenzierten Wert nachvollziehen – nicht, dass die Aussage oder Diagnose richtig ist. *Stützung Dok* ist eine Schlüsselwort-Heuristik. *Zusatz-Behaupt.* = Bewertungen, die keiner Wahrheits-Gruppe entsprechen und eine Ursache behaupten; *Bewertungen exakt* = alle erwarteten gefunden und keine Zusatzbehauptung. B0 kennt die Szenario-Scope-Angabe (Station/Variante) aus der Szenariodefinition, nicht aus der Frage.

## 2026-10-16 20:55 UTC · Modell gpt-5 · max_tokens 24000 · Szenarien S01-temperature-drift, S04-no-fault, S05-sensor-offset, S08-drift-and-bad-lot, S08w-drift-and-bad-lot-weak · 5 Läufe (4 regulär, 1 explorativ) · eingefrorener Datenstand je Szenario

**Reguläre Szenarien (Lösbarkeit erfüllt, nicht explorativ) – Gesamtquoten** (S01-temperature-drift, S04-no-fault, S05-sensor-offset, S08-drift-and-bad-lot, 4 Läufe)

| System | Abschluss | Befund korrekt | Bewertungen korrekt | Ursache | Zusatz-Behaupt. Ø | Bewertungen exakt | Zurückhaltung ok | Pflicht-Tools | Zitat vorh. | Herkunft live | Herkunft Dok | Stützung Dok | Nächster Test | Diagnose-Konsistenz | Ø s | Ø $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B0 | 100 % | 100 % | 100 % | 100 % | 0.00 | 100 % | 100 % | 75 % | 100 % | 100 % (6/6) | 100 % (5/5) | 40 % (2/5) | 75 % | n/a | 0.0 | 0.000 |

**Explorative Läufe (als explorativ markiert oder Lösbarkeit nicht erfüllt) – separat, nicht in der Gesamtquote** (S08w-drift-and-bad-lot-weak, 1 Läufe)

| System | Abschluss | Befund korrekt | Bewertungen korrekt | Ursache | Zusatz-Behaupt. Ø | Bewertungen exakt | Zurückhaltung ok | Pflicht-Tools | Zitat vorh. | Herkunft live | Herkunft Dok | Stützung Dok | Nächster Test | Diagnose-Konsistenz | Ø s | Ø $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B0 | 100 % | 100 % | 100 % | 100 % | 0.00 | 100 % | 100 % | 100 % | 100 % | 100 % (3/3) | 100 % (2/2) | 0 % (0/2) | 100 % | n/a | 0.0 | 0.000 |

Je Szenario: abgeschlossen / Befund korrekt / Bewertungen exakt (über Wiederholungen); (E) = explorativ:

| Szenario | B0 |
|---|---|
| S01-temperature-drift | 1 / 1 / 1 von 1 |
| S04-no-fault · Detektor-Fehlalarm auf unveränderter Linie: nein | 1 / 1 / 1 von 1 |
| S05-sensor-offset | 1 / 1 / 1 von 1 |
| S08-drift-and-bad-lot | 1 / 1 / 1 von 1 |
| S08w-drift-and-bad-lot-weak (E) | 1 / 1 / 1 von 1 |

Lesehilfe: *regulär* = Lösbarkeit erfüllt und nicht explorativ; nur diese Läufe bilden die Gesamtquoten. *Abschluss* = auswertbarer Report ohne Fehler; *Diagnose-Konsistenz* = Mehrheitsanteil nur über abgeschlossene Läufe; *Zurückhaltung ok* = 'unklar' genau dann, wenn die Wahrheit es verlangt; *Herkunft live* n/a für Systeme ohne Referenzen (V1-Schema). *Herkunft* heißt: Die automatische Prüfung konnte die angegebene Quelle bzw. den referenzierten Wert nachvollziehen – nicht, dass die Aussage oder Diagnose richtig ist. *Stützung Dok* ist eine Schlüsselwort-Heuristik. *Zusatz-Behaupt.* = Bewertungen, die keiner Wahrheits-Gruppe entsprechen und eine Ursache behaupten; *Bewertungen exakt* = alle erwarteten gefunden und keine Zusatzbehauptung. B0 kennt die Szenario-Scope-Angabe (Station/Variante) aus der Szenariodefinition, nicht aus der Frage.

## 2026-10-17 09:08 UTC · Modell gpt-5 · max_tokens 24000 · Szenarien S01-temperature-drift, S04-no-fault, S05-sensor-offset, S08-drift-and-bad-lot, S08w-drift-and-bad-lot-weak · 60 Läufe (48 regulär, 12 explorativ) · eingefrorener Datenstand je Szenario

**Reguläre Szenarien (Lösbarkeit erfüllt, nicht explorativ) – Gesamtquoten** (S01-temperature-drift, S04-no-fault, S05-sensor-offset, S08-drift-and-bad-lot, 48 Läufe)

| System | Abschluss | Befund korrekt | Bewertungen korrekt | Ursache | Zusatz-Behaupt. Ø | Bewertungen exakt | Zurückhaltung ok | Pflicht-Tools | Zitat vorh. | Herkunft live | Herkunft Dok | Stützung Dok | Nächster Test | Diagnose-Konsistenz | Ø s | Ø $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B0 | 100 % | 100 % | 100 % | 100 % | 0.00 | 100 % | 100 % | 75 % | 100 % | 100 % (18/18) | 100 % (15/15) | 40 % (6/15) | 75 % | 100 % | 0.0 | 0.000 |
| B1 | 100 % | 0 % | 0 % | 0 % | 0.00 | 0 % | 42 % | 25 % | 75 % | n/a | 93 % (51/55) | 18 % (10/55) | 67 % | 92 % | 85.1 | 0.062 |
| V1S | 100 % | 67 % | 42 % | 67 % | 0.50 | 42 % | 67 % | 25 % | 92 % | 90 % (158/175) | 100 % (61/61) | 56 % (34/61) | 100 % | 92 % | 159.8 | 0.129 |
| V2 | 100 % | 75 % | 67 % | 100 % | 0.25 | 67 % | 75 % | 100 % | 100 % | 94 % (155/165) | 100 % (47/47) | 64 % (30/47) | 100 % | 100 % | 155.8 | 0.124 |

**Explorative Läufe (als explorativ markiert oder Lösbarkeit nicht erfüllt) – separat, nicht in der Gesamtquote** (S08w-drift-and-bad-lot-weak, 12 Läufe)

| System | Abschluss | Befund korrekt | Bewertungen korrekt | Ursache | Zusatz-Behaupt. Ø | Bewertungen exakt | Zurückhaltung ok | Pflicht-Tools | Zitat vorh. | Herkunft live | Herkunft Dok | Stützung Dok | Nächster Test | Diagnose-Konsistenz | Ø s | Ø $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B0 | 100 % | 100 % | 100 % | 100 % | 0.00 | 100 % | 100 % | 100 % | 100 % | 100 % (9/9) | 100 % (6/6) | 0 % (0/6) | 100 % | 100 % | 0.0 | 0.000 |
| B1 | 100 % | 0 % | 0 % | 0 % | 0.00 | 0 % | 33 % | 0 % | 100 % | n/a | 86 % (12/14) | 14 % (2/14) | 33 % | 67 % | 135.1 | 0.083 |
| V1S | 100 % | 100 % | 0 % | 100 % | 0.00 | 0 % | 100 % | 0 % | 100 % | 100 % (56/56) | 100 % (17/17) | 53 % (9/17) | 100 % | 100 % | 192.7 | 0.193 |
| V2 | 100 % | 100 % | 100 % | 100 % | 0.00 | 100 % | 100 % | 100 % | 100 % | 100 % (54/54) | 100 % (16/16) | 50 % (8/16) | 100 % | 100 % | 171.8 | 0.149 |

Je Szenario: abgeschlossen / Befund korrekt / Bewertungen exakt (über Wiederholungen); (E) = explorativ:

| Szenario | B0 | B1 | V1S | V2 |
|---|---|---|---|---|
| S01-temperature-drift | 3 / 3 / 3 von 3 | 3 / 0 / 0 von 3 | 3 / 3 / 3 von 3 | 3 / 3 / 3 von 3 |
| S04-no-fault · Detektor-Fehlalarm auf unveränderter Linie: nein | 3 / 3 / 3 von 3 | 3 / 0 / 0 von 3 | 3 / 2 / 2 von 3 | 3 / 3 / 3 von 3 |
| S05-sensor-offset | 3 / 3 / 3 von 3 | 3 / 0 / 0 von 3 | 3 / 0 / 0 von 3 | 3 / 0 / 0 von 3 |
| S08-drift-and-bad-lot | 3 / 3 / 3 von 3 | 3 / 0 / 0 von 3 | 3 / 3 / 0 von 3 | 3 / 3 / 2 von 3 |
| S08w-drift-and-bad-lot-weak (E) | 3 / 3 / 3 von 3 | 3 / 0 / 0 von 3 | 3 / 3 / 0 von 3 | 3 / 3 / 3 von 3 |

Lesehilfe: *regulär* = Lösbarkeit erfüllt und nicht explorativ; nur diese Läufe bilden die Gesamtquoten. *Abschluss* = auswertbarer Report ohne Fehler; *Diagnose-Konsistenz* = Mehrheitsanteil nur über abgeschlossene Läufe; *Zurückhaltung ok* = 'unklar' genau dann, wenn die Wahrheit es verlangt; *Herkunft live* n/a für Systeme ohne Referenzen (V1-Schema). *Herkunft* heißt: Die automatische Prüfung konnte die angegebene Quelle bzw. den referenzierten Wert nachvollziehen – nicht, dass die Aussage oder Diagnose richtig ist. *Stützung Dok* ist eine Schlüsselwort-Heuristik. *Zusatz-Behaupt.* = Bewertungen, die keiner Wahrheits-Gruppe entsprechen und eine Ursache behaupten; *Bewertungen exakt* = alle erwarteten gefunden und keine Zusatzbehauptung. B0 kennt die Szenario-Scope-Angabe (Station/Variante) aus der Szenariodefinition, nicht aus der Frage. *Pflicht-Tools* beschreibt die Werkzeugnutzung des Agenten (wurden die für das Szenario erwarteten Werkzeuge aufgerufen), nicht die Diagnosequalität; für B0, das direkt die Ingenieurfunktionen aufruft, ist die Quote strukturell bedingt (z. B. 75 %, weil S04 `get_station_stats` erwartet) und keine Aussage über seine Bewertungen.

Nachträgliche Auswertung Lauf 4 (`evals/rescore.py`, regulär = 48 Läufe):

| System | Bewertungen gefunden | Zusatz-Behaupt. Ø | Läufe mit Zusatzbehauptung | Bewertungen exakt | Befund korrekt |
|---|---|---|---|---|---|
| B0 | 100 % | 0.00 | 0/12 | 100 % | 100 % |
| B1 | 0 % | 0.00 | 0/12 | 0 % | 0 % |
| V1S | 42 % | 0.50 | 6/12 | 42 % | 67 % |
| V2 | 67 % | 0.25 | 3/12 | 67 % | 75 % |

Zusatzbehauptungen im Detail:
- v1s/S04-no-fault/r0: {'station': 2, 'variant': 'B', 'lot': None} valid/suspected/unknown
- v1s/S05-sensor-offset/r0: {'station': 2, 'variant': 'B', 'lot': None} invalid_temperature/none_assessable/station_temperature
- v1s/S05-sensor-offset/r1: {'station': 2, 'variant': 'B', 'lot': None} invalid_temperature/none_assessable/station_temperature
- v1s/S05-sensor-offset/r2: {'station': 2, 'variant': 'B', 'lot': None} invalid_temperature/none_assessable/station_temperature
- v2/S05-sensor-offset/r0: {'station': 2, 'variant': 'B', 'lot': None} invalid_temperature/none_assessable/station_temperature
- v2/S05-sensor-offset/r1: {'station': 2, 'variant': 'B', 'lot': None} invalid_temperature/none_assessable/station_temperature
- v2/S05-sensor-offset/r2: {'station': 2, 'variant': 'B', 'lot': None} invalid_temperature/none_assessable/station_temperature
- v1s/S08-drift-and-bad-lot/r0: {'station': 2, 'variant': 'B', 'lot': 'L2441-03'} valid/suspected/connector_lot
- v1s/S08-drift-and-bad-lot/r2: {'station': 2, 'variant': 'B', 'lot': None} valid/suspected/connector_lot

### Auswertung von Lauf 4 – 17.10.2026, nach Lesen der fehlerhaften Antworten

**Funktionskriterium aus CONCEPT §10 nicht erfüllt.** V2 exakt S04 3/3 (= B0), S05 0/3 (B0 3/3), S01 ohne Zusatzbehauptung 3/3. Die vorab festgelegten Bewertungen bleiben bestehen. Alle 29 Antworten, die „exakt“ verfehlen, sind gelesen (23 reguläre, sechs explorative). Offline-Rescore bestätigt die Tabelle. Details und Belegpfade: [RUN4_REVIEW.md](RUN4_REVIEW.md).

- **S05 / V2 / r0–r2:** Der Agent erkennt den Sensorverdacht in allen drei Antworten; `describe_signal` liefert „decoupled“ und nennt den Widerspruch zwischen gemeldetem T1 und Ruhestrom. Die Reports enthalten dennoch gleichzeitig `invalid_temperature/none_assessable/station_temperature` und `unknown/suspected/sensor_t1` für dieselbe Gruppe. Erwartet war `unknown/none/sensor_t1`. Konkurrierende Erklärungen werden wie gleichzeitige Befunde festgeschrieben, daraus wird `mixed`. Das ist eine Interpretations-/Reportinkonsistenz; „Sensorfehler nicht erkannt“ wäre zu grob.
- **S08 / V2 / r1:** Temperaturbewertung korrekt, Losbewertung nur `suspected`. Die gewählte Abfrage Station 2/B sieht acht E-120-Fails im Los und unterschreitet die Werkzeugschwelle von zehn. Die stationsübergreifende Abfrage von B0 sieht 13 und liefert „konzentriert“. V2s Vorsicht passt zur engeren Datenabfrage; es fehlt die Untersuchung des Loses über Stationen hinweg. Werkzeugname aufgerufen bedeutet nicht Untersuchungsbereich vollständig.
- **V1S:** S04/r0 überinterpretiert die Grundrate als Gruppenbefund; S05/r0–r2 übernimmt die gemeldete Temperatur als Übertemperatur; S08 fehlt die starke, korrekt eingegrenzte Losbewertung, teilweise mit zusätzlichen Losbehauptungen.
- **B1:** Das alte Schema erlaubt keine `assessments`. Auf S04 weisen alle drei Texte den behaupteten Anstieg zurück; `information` statt `unclear` wird dennoch als falscher Befund gezählt. Die eingefrorene Quote bleibt 0 %, ist aber keine allgemeine Inhaltsgenauigkeit.

**Die Vergleiche:** B0 erreicht regulär 12/12 exakt, V2 8/12. V1S → V2 verbessert sich von 5/12 auf 8/12 (S04 +1, S08 +2); S05 bleibt bei 0/3, obwohl die Sensorhypothese mit Werkzeugen sichtbar wird. Latenz/Kosten unterscheiden sich in diesem Lauf nur wenig (159,76 → 155,77 s; 0,12865 → 0,12448 USD). Ein diagnostischer Zusatznutzen gegenüber dem Regelwerk ist für diese bekannten Muster nicht gezeigt. S08w bleibt trotz erfüllter Voraussetzungen separat explorativ.

**Grenzen:** V2s Herkunft live 155/165 und Dokumente 47/47 schließen einen widersprüchlichen Gesamtbefund nicht aus. „Ursache 100 %“ prüft vorhandene Ursachennamen, nicht Widerspruchsfreiheit. „Nächster Test“ ist ein Schlüsselwortcheck. `check_validity` bewertet FAIL-Umklassifizierung, nicht Sensorvertrauen oder sämtliche PASS-Messungen. Diese Einschränkungen sind im Review erläutert.

**Archivnotiz:** `code.dirty=true`; der getrackte Anwendungs-/Eval-Code im heutigen Arbeitsverzeichnis entspricht dem archivierten Commit `d8ef3bd`, ein damaliger Dirty-Diff ist nicht archiviert. Die Latenzen, Wartezeiten, Snapshots und Dateizeit ergeben rund zwei Stunden (09:08–11:08 UTC, 11:08–13:08 Uhr Berlin). Berechnete Gesamtkosten aller 60 Läufe: 5,06212 USD.

**Abschluss:** Die Prüfphase wird mit dem negativen Funktionskriterium abgeschlossen. Ein neuer bezahlter Lauf wird daraus nicht abgeleitet. Als mögliche spätere Verbesserung ist zuerst eine Konsistenzprüfung der Endbewertung sinnvoll; ein Re-Test derselben Einheit bleibt eine getrennte Erweiterung.
