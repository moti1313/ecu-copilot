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
| **V1S → V2** (zusätzlich Ingenieur-Werkzeuge) | Bewertungen gefunden 83 % → 100 %, exakt 83 % → 83 % (V2: 1 Zusatzbehauptung in 6); Pflicht-Werkzeuge 0 % → 100 %; Evidenzstärke für das Los 2/3 „strong" → 3/3 „strong"; Latenz 108 → 92 s; Kosten 0,146 → 0,121 $ | Die Werkzeuge machen die Antwort **vollständiger, schneller und billiger** (weniger Rohdaten im Kontext) und kalibrieren die Evidenzstärke – sie verhindern aber nicht jede Überinterpretation (siehe unten). |
| **B0 → V2** (Regelwerk vs. Agent) | S01: beide 3/3. S08: B0 1/2 (Temperaturregel griff bei 3 E-204-Fails nicht – Lösbarkeitskriterium nicht erfüllt), V2 3/3 vollständig. B0: 0 s, 0 $; V2: 92 s, 0,12 $ | Bei erfülltem Kriterium und bekanntem Muster ist B0 nicht zu schlagen. V2s Vorteil zeigte sich hier nur im Schwachsignal-Fall – das ist ein Hinweis, kein Nachweis. Der Nutzen des Agenten muss an S04–S10 gemessen werden. |

**Die fehlerhaften Antworten, gelesen**
- *V2 / S01 / r1 („mixed", Zusatzbehauptung):* Der Agent erklärte E-204 korrekt als ungültig und fügte eine zweite Bewertung „gültig / vermutet / unbekannt" für die **drei verbleibenden Hintergrund-Fails** (2× E-310, 1× E-401) hinzu – also für die normale Grundrate. Überinterpretation des Rauschens. → Prompt-Regel 13 (Grundrate ist keine Bewertung), Prompt-Version 2026-10-16.3. Ob die Regel wirkt, zeigt erst der nächste Lauf.
- *V2 / S08 / r2 („Zitat vorh." = nein):* **Metrikfehler, kein Agentenfehler.** Der Agent zitierte „TS-DCU-EOL 4.2" (ohne §, wie der Prompt es verlangt); die Wahrheit prüfte auf „§4.2". Vergleich normalisiert; die Zeile wäre mit korrekter Metrik bestanden (V2 „Zitat vorh." → 100 %).
- *V1S / S08 / r1 (1/2):* Los-Bewertung „vermutet" statt „stark". Ohne `cluster_failures` sah V1S nur ≤ 40 Rohzeilen und blieb vorsichtig – vertretbar, aber unter dem Kriterium. Genau hier helfen die Werkzeuge (V2: 3/3 „stark").
- *B0 / S08 (1/2):* Temperaturregel verlangt ≥ 5 E-204-Fails; es gab 3 (Lösbarkeit nicht erfüllt). Kein Regelfehler, ein Szenario-Setup-Problem (Los-Einheiten fallen in Schritt 1 aus und erreichen die Ruhestrommessung nicht).

**Was noch nicht aussagekräftig ist:** „Stützung Dok" (Schlüsselwort-Heuristik, 21–48 %), Diagnose-Konsistenz (bei 3 Läufen grob), alles über zwei Szenarien hinaus.

**Konsequenzen (Entscheidung ausstehend):** (1) Prompt-Regel 13 und Metrik-Normalisierung sind eingebaut, kein neuer Lauf, bis weitere Szenarien existieren. (2) S08-Setup: Wartezeit 300 s oder Los-Rate 0,15, damit das Lösbarkeitskriterium erfüllt ist. (3) Nächster Benchmark erst mit S04/S05 (kein Fehler, Sensorfehler) – dort entscheidet sich, ob der Agent gegenüber B0 einen Nutzen hat.
