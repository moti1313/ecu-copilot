# ECU Copilot präsentieren

**Einstieg:** [Präsentation als PDF](ECU-Copilot-Praesentation.pdf) · [Alle Folien auf einen Blick](Uebersicht.png) · [Sprechtext und Dashboard-Demo](SPRECHTEXT.md)

Neun visuelle Folien erklären den Prototyp: große Diagramme, kurze Beschriftungen und ein durchgehendes Beispiel. Weiß, Schwarz und Rostrot; die Erklärungen stehen im separaten Sprechtext. Umfang: etwa **5–7 Minuten Vortrag**, danach eine kurze Dashboard-Demo. Stand: 17.10.2026.

**E-204 auf Folie 1 ist ein illustratives Beispiel:** 483 µA, Limit 450 µA und T1 35 °C. Diese Werte dienen der Erklärung und sind kein zitierter Benchmarkbefund. Benchmarkzahlen werden aus dem jeweiligen geprüften Lauf separat ergänzt.

## Die Folien

| Folie | Frage | Eigenständiges Diagramm |
|---|---|---|
| 1 | E-204: Gerät defekt oder Prüfung ungültig? | [Prüfbeispiel](diagrams/01-konzept.svg) |
| 2 | Wer nutzt das System, welche Datenquellen gibt es? | [Systemkontext](diagrams/02-systemkontext.svg) |
| 3 | Was läuft wo? | [Laufzeitarchitektur](diagrams/03-laufzeitarchitektur.svg) |
| 4 | Wie werden aus Daten Belege und ein Befund? | [Datenfluss](diagrams/04-datenfluss.svg) |
| 5 | Was passiert nach dem Klick auf „Untersuchung starten“? | [Sequenz](diagrams/05-untersuchungsablauf.svg) |
| 6 | Quelle gefunden. Ursache offen. | [Belege und Grenzen](diagrams/06-belege-und-grenzen.svg) |
| 7 | Wie vergleichen wir Regeln und Agenten? | [Benchmark](diagrams/07-benchmark.svg) |
| 8 | Welchem Weg folgen wir im Dashboard? | [Demo-Pfad](diagrams/08-stand-und-demo.svg) |
| 9 | Welche Forschung hat die Gestaltung beeinflusst? | [Forschungsbezug](diagrams/09-forschung.svg) |

Jede Folie liegt zusätzlich als PNG im selben Ordner. SVG eignet sich zum Einfügen in PowerPoint oder LibreOffice, weil Schrift und Linien beim Vergrößern scharf bleiben. PNG ist die einfachere Alternative bei Importproblemen. Die PDF kann direkt im Vollbild präsentiert werden. Die SVG-Dateien enthalten Text und Vektoren, keine Bildschirmfotos.

## Fachliche Grundlage

- [Umgesetzte Architektur](../ARCHITECTURE_CURRENT.md): Systemkontext, Dienste, Datenfluss, Sequenz und Grenzen; editierbare Mermaid-Diagramme.
- [Recherche und konkrete Verbesserungen](RECHERCHE.md): Primärquellen, Lesestand und begründete Gestaltungsentscheidungen.
- [Vorhandener Zielentwurf](../ARCHITECTURE.md): enthält spätere Erweiterungen; in der Präsentation als solche gekennzeichnet.
- [Gemessene Ergebnisse](../RESULTS.md): bei Abschluss eines konkreten Benchmarklaufs dessen Tabelle und Archiv separat heranziehen.

**Ein Satz für die Präsentation:**

> „Ich zeige einen Integrationsprototyp für Prüfingenieure: Er verbindet simulierte Prüfungen, technische Dokumente und Analysewerkzeuge zu einer Untersuchung mit nachvollziehbaren Belegen. Die Bewertung erfolgt auf kontrollierten Szenarien; eine Validierung im realen Werk steht noch aus.“

## Präsentation reproduzieren

```bash
python3 scripts/build_presentation.py
```

Der Export benötigt **Matplotlib in diesem Python**, verwendet dessen nichtinteraktives Agg-Backend und erzeugt ausschließlich Dateien unter `design/presentation/`. Für die laufende Anwendung wird keine Abhängigkeit ergänzt. Der Generator kontaktiert weder Twin noch LLM und verändert keine Szenarien, Prompts oder Benchmarkmetriken.

Der Export prüft, ob Text innerhalb der Folien und beschrifteten Karten bleibt. `manifest.json` enthält die Folienliste, den Git-Stand und SHA-256-Prüfsummen der herangezogenen Implementierungsdateien. Der Git-Stand ist der beim Export sichtbare HEAD; die Prüfsummen bezeichnen die tatsächlich gelesenen Dateien. Bei späteren Codeänderungen die Aussagen erneut abgleichen und exportieren.

## Was diese Unterlagen verbessern

Der Ist-Zustand ist vom Zielentwurf getrennt. Die Darstellung zeigt den Browserzugriff auf den Twin, den externen Modellaufruf, die lokale Dokumentensuche und die begrenzte Belegprüfung ausdrücklich. Simulation, Benchmark und menschliche Entscheidung sind eigene Schritte. Es wird weder ein physisch angebundener Digital Twin noch eine bereits ausgeführte Wiederholungsprüfung behauptet.
