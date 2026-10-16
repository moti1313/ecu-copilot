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
