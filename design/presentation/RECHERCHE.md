# Recherche für Architektur und Präsentation

Geprüft am **17.10.2026**. Zweck: den vorhandenen Prototyp besser erklären und seine Grenzen präzise benennen. Die folgenden Ableitungen sind Gestaltungsentscheidungen für dieses Projekt, keine Replikation der Forschungsarbeiten.

## 1. Primärquellen und Ableitungen

| Quelle | Geprüfter Inhalt | Konsequenz für diese Unterlagen | Grenze der Übertragung |
|---|---|---|---|
| Simon Brown: [C4 – Diagrams](https://c4model.com/diagrams) | Architektur über Systemkontext, Container und weitere Zoomstufen erklären; zusätzliche dynamische Sichten | Getrennte Folien für Kontext, Laufzeit und Sequenz | Eigene vereinfachte Diagramme, keine formale C4-Konformitätsbehauptung. Ein C4-Container bezeichnet eine Laufzeiteinheit, nicht zwingend einen Docker-Container. |
| Shyalika, Jaimini, Henson, Sheth: [CausalPulse, arXiv:2603.29755v1](https://arxiv.org/html/2603.29755) | Architektur, Agentenfähigkeiten, Orchestrierung und Evaluation: LLM-Planung wird mit spezialisierten Diagnoseverfahren verbunden. Die etwa 98 % betreffen Orchestrierungs-/Workflowkriterien | Werkzeugberechnung und Modellinterpretation im Datenfluss ausdrücklich trennen; Ablaufqualität und Diagnosekorrektheit getrennt behandeln | Unser Projekt implementiert weder dessen Multi-Agent-System noch dessen kausale Strukturlernverfahren. Die Erfolgszahlen sind keine Genauigkeitsangabe für unseren Copilot. |
| Jansson, Strandberg, Sörensen, Enoiu, Afzal: [Supporting Industrial Test-Failure Analysis with LLM-Based Systems, arXiv:2609.21843v1](https://arxiv.org/html/2609.21843v1) | Industrieller Erfahrungsbericht: zwei reale Fehlerfälle, sechs Praktiker, Vergleich eines Agenten mit einer orchestrierten Variante. Kein durchgängiger wahrgenommener Qualitätsvorteil der aufwendigeren Variante | Ein Agent als verständlicher Ausgangspunkt; Belege, Klarheit und Aufwand gemeinsam zeigen | Die kleine Fallstudie beweist keine generelle Überlegenheit eines einzelnen Agenten. Unsere synthetische Evaluation ersetzt kein Praktikerfeedback. |
| Abboush, Knieke, Rausch: [Advancing real-time validation of automotive software systems via continuous integration and intelligent failure analysis, Scientific Reports 15, 32936 (2025)](https://www.nature.com/articles/s41598-025-21416-5) | Methoden, Reportgenerierung und Ergebnisse: CI-gestützte HiL-Tests, Denoising-Autoencoder und Modelle zur Klassifikation/Clusterung von Sensorfehlern | Automatische Erkennung als eigenständige Aufgabe erklären; die Untersuchung mit Quellen und nächsten Schritten als unseren Integrationsfokus darstellen | Unser Simulator ist kein HiL-Prüfstand. B0 ist eine Regelbaseline, keine Nachimplementierung dieser ML-Pipeline. Keine direkte Rangfolge der Genauigkeitszahlen. |
| W3C: [PROV-Overview](https://www.w3.org/TR/prov-overview/) | Provenienz beschreibt an der Entstehung von Daten beteiligte Objekte, Vorgänge und Personen und kann Qualitätsbewertungen unterstützen | Datenherkunft, inhaltliche Stützung und bestätigte Ursache getrennt darstellen | Wir verwenden eigene Referenzen. Kein RDF-/PROV-O-Export und keine vollständige semantische Verifikation. |
| Guodong Shao: [NIST AMS 400-2 (2021), §2.1](https://nvlpubs.nist.gov/nistpubs/ams/NIST.AMS.400-2.pdf) | Begriff und Anwendungsbeispiele industrieller digitaler Zwillinge; Darstellung und Synchronisation eines beobachtbaren Fertigungselements | Unseren Datenlieferanten präzise als Prüflinien-Simulator / Twin-Prototyp bezeichnen; physische Anbindung als spätere Validierung markieren | Das Dokument diskutiert den damaligen ISO/DIS-23247-Stand. Es wird hier als fachliche Einordnung verwendet, nicht als Nachweis einer aktuellen Normerfüllung. |

Lesestand: Die genannten relevanten Abschnitte bzw. HTML-Volltexte sind zugänglich und wurden für diese Aussagen geprüft. Bei NIST wurde insbesondere der Begriffsabschnitt §2.1 gelesen; eine vollständige Normprüfung wurde nicht durchgeführt. Der ältere, breitere Literaturstand steht in [RESEARCH.md](../RESEARCH.md); sein Lesestand bleibt separat erhalten.

## 2. Verbesserungen am konkreten Projektverständnis

1. **Ist und Ziel auseinanderhalten.** Der alte Architekturentwurf enthält beispielsweise `/retest`, `simulate_retest`, Firmwarestörungen und einen Router. Diese Funktionen fehlen im betrachteten Code. Die neue Ist-Architektur und Folie 8 kennzeichnen sie als Ausblick.
2. **Den tatsächlichen Datenfluss zeigen.** Der Browser liest Twin-Daten direkt; Untersuchungen gehen an die Copilot-API. Der externe Modellanbieter erhält den verwendeten Kontext. Chroma und Ingenieurfunktionen sind Bibliotheken im Copilot-Dienst, keine zusätzliche Service-Landschaft.
3. **Live und Evaluation unterscheiden.** Nur der Benchmark besitzt den gemeinsamen `SnapshotTwin`. Die Live-Untersuchung fragt Daten je Werkzeugaufruf ab. Daraus folgt kein atomarer Datenstand zum Klickzeitpunkt.
4. **Belegprüfung präzise erklären.** Der Verifier kann Referenzen und bestimmte Vergleiche prüfen. Dokumentstützung über Begriffsüberlappung bleibt eine Heuristik. Die nächste sinnvolle Prüfung ist daher ein Vorschlag und keine bereits bestätigte Ursache.
5. **Messung und Nutzen trennen.** Token-Nutzung, Laufzeit und Treffer im Simulator werden erhoben. Eine behauptete Zeitersparnis für Ingenieure erfordert einen gesonderten Nutzertest. Drei Modellwiederholungen auf demselben Snapshot sind keine unabhängigen Fertigungsfälle.

Diese Verbesserungen sind in den Präsentationsunterlagen umgesetzt. Sie verändern weder Lauf 4 noch seine vorab festgelegten Metriken.

## 3. Ehrliche Formulierungen

| Thema | Geeignete Formulierung |
|---|---|
| Daten | „Die bisherigen Prüfdaten und technischen Unterlagen sind synthetisch. Damit kann ich kontrollierte Fehlersituationen untersuchen.“ |
| Eigener Beitrag | „Ich habe den Datenfluss von Prüfungen und Dokumenten über Analysewerkzeuge bis zum belegten Untersuchungsbericht integriert.“ |
| Forschung | „CausalPulse und die Westermo-Arbeit haben die Trennung von Planung, Werkzeugen und menschlicher Beurteilung beeinflusst.“ |
| Herkunft | „Die Prüfung konnte den referenzierten Wert beziehungsweise Abschnitt wiederfinden.“ |
| Diagnose | „Das ist die anhand der verfügbaren Belege vorgeschlagene Erklärung. Eine unabhängige Gegenprüfung steht noch aus.“ |
| Qualität | „Ich vergleiche den Agenten mit einem Regelwerk und anderen Konfigurationen auf denselben Szenariodaten.“ |
| Nutzen | „Der angestrebte Nutzen ist eine leichter nachvollziehbare Untersuchung. Eine gemessene Zeitersparnis im realen Werk behaupte ich noch nicht.“ |

## 4. Prioritäten nach dem Präsentationspaket

Für diesen Prototypabschluss: den festgelegten Benchmark auswerten und die Demo verständlich erklären. Als spätere Weiterentwicklung wären ein fester Datenstand pro Live-Untersuchung, eine persistente Identität beim Re-Test und die Validierung mit realen Daten und Nutzern sinnvoll. Daraus entsteht keine zusätzliche Voraussetzung für die hier angefragten Diagramme und Unterlagen.
