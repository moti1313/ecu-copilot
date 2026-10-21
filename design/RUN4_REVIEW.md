# Lauf 4 – Auswertung nach Lesen der Antworten

Stand: 17.10.2026. Archiv: `data/evals/bench-20261017-090812/`. Die vorab festgelegte Bewertung bleibt erhalten. Für diese Auswertung wurden keine Modellaufrufe ausgeführt und weder Prompt, Szenarien noch Metriken geändert.

## Ergebnis

**Das Funktionskriterium ist nicht erfüllt.** B0 erreicht auf den vier regulären Szenarien 12/12 exakte Bewertungen, V2 8/12. V2 nennt bei S05 in allen drei Antworten den Sensorfehler, erzeugt aber zugleich eine zusätzliche Temperaturursache und einen inkonsistenten Gesamtbefund. „Der Agent erkennt den Sensorfehler nicht“ beschreibt das beobachtete Versagen deshalb ungenau.

| Szenario | B0 exakt | B1 exakt | V1S exakt | V2 exakt |
|---|---:|---:|---:|---:|
| S01 Temperaturdrift | 3/3 | 0/3 | 3/3 | 3/3 |
| S04 unveränderte Linie | 3/3 | 0/3 | 2/3 | 3/3 |
| S05 Sensor-Offset | 3/3 | 0/3 | 0/3 | 0/3 |
| S08 Drift und Los | 3/3 | 0/3 | 0/3 | 2/3 |
| **Regulär gesamt** | **12/12** | **0/12** | **5/12** | **8/12** |
| S08w, separat explorativ | 3/3 | 0/3 | 0/3 | 3/3 |

V2 erreicht S04 exakt 3/3 und S01 ohne Zusatzbehauptung 3/3. Der verpflichtende Vergleich auf S05 geht jedoch 0/3 gegen 3/3 für B0 aus. Die getrennte explorative Zeile ändert dieses Ergebnis nicht.

## Was geprüft wurde

- 60 archivierte Läufe und fünf Szenario-Snapshots; alle Reports sind als abgeschlossen gespeichert, 48 Läufe sind regulär, 12 explorativ.
- Alle **29 Antworten mit nicht exakter Bewertung** gelesen: 23 reguläre und sechs explorative. Bei S05/V2 und dem fehlgeschlagenen S08/V2-Lauf zusätzlich Werkzeugparameter und relevante vollständige Ausgaben gelesen.
- `evals/rescore.py` ausschließlich offline erneut ausgeführt; die veröffentlichten Quoten und Zusatzbehauptungen bestätigt.
- S05-Messfenster und S08-Loskonzentration mit den archivierten Snapshots offline nachvollzogen. Aktuelle und archivierte Szenariodefinitionen stimmen überein.

Das ist eine gezielte Fehleranalyse, keine unabhängige fachliche Verifikation jedes einzelnen Satzes aller Reports und keine neue Wirksamkeitsmessung.

## 1. S05: erkanntes Sensorproblem, widersprüchlich festgeschrieben

### Die Belege sind verfügbar

V2 ruft `describe_signal(station=2, variant="B", minutes=20)` in allen drei Wiederholungen auf. Die identische Ausgabe enthält:

- `iq_t1_relation: "decoupled"`, Modellverhältnis 0,06;
- erwarteten Ruhestrom bei gemeldetem T1 von 348,4 µA gegenüber gemessenen 331,1 µA;
- 96/480 Ergebnisse mit gemeldetem T1 außerhalb des Temperaturfensters;
- den ausdrücklichen Hinweis, T1 zu prüfen, bevor Ergebnisse aufgrund dieses Messwertes als ungültig behandelt werden.

Die Daten wurden also nicht übersehen. Alle drei Antworten stufen die Sensorhypothese im Hypothesenabschnitt als `strong` ein und schlagen einen externen Temperaturabgleich vor.

### Der strukturierte Report vermischt Alternativen und gleichzeitige Ursachen

Alle drei V2-Reports enthalten für dieselbe Gruppe Station 2/B diese beiden Bewertungen:

```text
invalid_temperature / none_assessable / station_temperature
unknown             / suspected       / sensor_t1
```

Erwartet war vorab:

```text
unknown / none / sensor_t1
```

Die erste Zeile schreibt eine Temperaturursache fest, obwohl der Report selbst die Temperaturmessung infrage stellt. Die zweite Zeile enthält den richtigen Ursachennamen, aber nicht die erwartete Bauteilbewertung. Ein Sensorproblem des Prüfstands darf nicht ohne zusätzliche Evidenz als Produktdefektverdacht derselben ECU-Gruppe erscheinen.

`derive_finding()` verdichtet die Kombination aus einer INVALID-Zeile und `suspected` deterministisch zu `mixed`. Die Verdichtung folgt ihrem implementierten Vertrag; die widersprüchlichen Eingaben stammen aus dem Modellreport. Zwei konkurrierende Erklärungen sind hier wie zwei gleichzeitige Befunde abgelegt. In S08 sind getrennte Gruppenbewertungen sinnvoll; dieses Muster wurde bei S05 unpassend angewendet.

Im Text ist eine vorsichtige Behandlung von Ergebnissen bei unzuverlässigem T1 nachvollziehbar. Daraus folgt jedoch keine bereits belegte reale Übertemperatur. Das ist ein Interpretations- und Reportproblem, nicht bloß ein fehlendes Wort im Antworttext. Der vorab festgelegte Fehlschlag bleibt bestehen.

### Auch die Werkzeuge haben unterschiedliche Geltungsbereiche

`check_validity()` klassifiziert vorhandene FAIL-Verdikte um. Es prüft weder die Verlässlichkeit des Temperatursensors noch alle PASS-Messungen auf Umweltgültigkeit; `classify_result()` gibt für PASS frühzeitig zurück. Im S05-Snapshot gibt es im 20-Minuten-Fenster keine E-204-Fails, aber 96 gemeldete Temperaturüberschreitungen. „0 INVALID“ aus diesem Werkzeug bedeutet deshalb nicht „alle Ruhestrommessungen sind nachweislich gültig“.

Die automatische Herkunftsprüfung kann die zugrunde liegenden Werte finden. Sie entscheidet nicht über den Konflikt zwischen Messpfadvertrauen, bedingter Gültigkeitsregel und Ursachenbehauptung. Hier bleibt eine Lücke zwischen den berechneten Merkmalen und der abschließenden Bewertung.

## 2. S08 / V2 / Wiederholung 1: unterschiedliche Untersuchungsbereiche

Temperatur und Los werden beide erkannt. Die Losbewertung lautet aber `suspected` statt des vorab geforderten `strong`.

| Datenabfrage für Los L2439-07, Code E-120 | Fälle im Los | Rate Ratio | z | Werkzeug: konzentriert |
|---|---:|---:|---:|---|
| V2: Station 2/B, 60 Minuten | 8 | 20,78 | 8,10 | nein |
| B0: alle Stationen/B, 30 Minuten | 13 | 12,20 | 8,06 | ja |

Das Werkzeug verlangt unter anderem mindestens zehn Fehlerfälle. V2s vorsichtigere Einstufung passt damit zu seiner engeren Abfrage. Für die erwartete stationsübergreifende Losbewertung fehlte eine entsprechende Erweiterung des Untersuchungsbereichs. B0 führt diese Abfrage fest aus.

Dieser Fall ist kein Nachweis, dass das Modell ein eindeutiges Werkzeugergebnis ignoriert hat. **Dasselbe verfügbare Snapshot bedeutet nicht dieselbe tatsächlich ausgewählte Evidenz.** Eine reine Prüfung des Werkzeugnamens erkennt die fehlende Abdeckung über Stationen hinweg nicht. Die veröffentlichte Bewertung bleibt 1/2 und nicht exakt; eine nachträgliche Absenkung von `strong` ist keine Lösung.

## 3. V1S: sieben reguläre Fehler

| Fälle | Beobachtetes Fehlermuster |
|---|---|
| S04 / r0 | Im Text wird der behauptete Anstieg korrekt zurückgewiesen. Der Report erklärt die normalen drei Einzelfehler dennoch zu `valid/suspected/unknown` für die Linie. Hintergrundfehler werden zum zusätzlichen Gruppenbefund. |
| S05 / r0–r2 | Gemeldete Temperatur wird als reale Übertemperatur übernommen. Alle drei Reports enthalten nur die Temperaturursache. Einzelne Antworten schlagen zwar eine Sensorplausibilisierung vor, nutzen sie aber nicht für die Einordnung. |
| S08 / r0 | Los L2439-07 nur `suspected`; zusätzlich wird das unauffällige Los L2441-03 als Ursache bewertet. |
| S08 / r1 | Richtiges Los, aber `suspected` statt `strong`. |
| S08 / r2 | Losursache ohne das konkret erwartete Los im Scope; ebenfalls `suspected`. |

Bei den drei explorativen S08w-Antworten wird das richtige Los genannt, aber durchgängig nur `suspected`. Sie bleiben außerhalb der Gesamtquote.

## 4. B1: 0 % ist kein Beleg für ausschließlich falsche Inhalte

B1 verwendet das ältere Schema ohne `assessments`. Die exakte Gruppenbewertung kann damit strukturell nicht erfüllt werden. Das ist bereits eine bekannte Einschränkung dieses Vergleichs.

Zusätzlich zeigen die Texte:

- Auf S04 weisen alle drei Antworten den behaupteten Anstieg zurück. `finding="information"` statt des geforderten `unclear` führt dennoch zu „Befund falsch“. Das gewünschte Zurückhalten ist hier inhaltlich vorhanden.
- Auf S01 wird Temperatur als plausible Ursache diskutiert; die Zeitfenster-Mittelwerte belegen die Einzelmessungs-Gültigkeit aber nicht. Die Antworten bleiben `unclear`.
- Auf S05 wird Übertemperatur aus der gemeldeten Temperatur abgeleitet; der Sensorfehler wird nicht als Ursache erkannt.
- Auf S08 und S08w werden teilweise mehrere Ursachen im Text beschrieben; das alte Befundfeld kann `mixed` nicht ausdrücken. Zusätzlich fehlen genaue Los-/Gültigkeitsbelege.

Die eingefrorenen Quoten werden nicht korrigiert. Für Aussagen über den Zusatznutzen der Analysewerkzeuge ist V1S gegenüber V2 der passendere Vergleich.

## 5. Was sich aus den Vergleichen sagen lässt

- **B0 gegenüber V2:** Auf den hier programmierten, bekannten Mustern ist B0 bei „exakt“ vorn, bei deutlich geringerem Rechenaufwand. Ein diagnostischer Zusatznutzen des Agenten ist hier nicht gezeigt.
- **V1S gegenüber V2:** V2 erreicht 8/12 statt 5/12 exakt; der Unterschied liegt in S04 (+1) und S08 (+2). Auf S05 wird die Sensorhypothese mit Analysewerkzeugen sichtbar, aber die Endbewertung bleibt falsch.
- **Aufwand:** Regulär V1S im Mittel 159,76 s und 0,12865 USD, V2 155,77 s und 0,12448 USD. Der kleine Unterschied in diesem Lauf rechtfertigt keine allgemeine Aussage „Werkzeuge machen schneller und billiger“.
- **Herkunft:** V2 live 155/165 und Dokumente 47/47 nachvollziehbar. Diese Quoten sind mit einem falschen oder widersprüchlichen Gesamtbefund vereinbar. Die Spalte „Ursache 100 %“ prüft lediglich, ob erwartete Ursachennamen irgendwo vorhanden sind; zusätzliche oder widersprüchliche Bewertungen werden dort nicht ausgeschlossen.
- **Nächster Test:** Die Metrik prüft Schlüsselwörter, keine fachliche Trennschärfe. Beispielsweise unterscheidet „dieselbe Einheit ist an einer kühleren Station unauffällig“ alleine nicht zwischen realer Übertemperatur und falscher Temperaturanzeige der ursprünglichen Station. Der unabhängige Fühlervergleich ist dafür entscheidend.

Diese vier regulären Szenarien mit je drei Wiederholungen sind weiterhin eine synthetische Funktionsprüfung. Eine Überlegenheit auf unbekannten Produktionsfällen oder eine Zeitersparnis für Ingenieure folgt daraus nicht.

## 6. Reproduzierbarkeit und Zeitangaben

Das Archiv nennt `d8ef3bd7853424e835b3eeb32aa0b1fd86973450`, Prompt `2026-10-16.3`, gpt-5, medium, 24 000 Tokens und **`dirty: true`**. Es enthält keine Git-Diff-Kopie, aus der sich die damaligen uncommitteten Änderungen vollständig rekonstruieren ließen. Der am 17.10.2026 für diese Auswertung geprüfte getrackte Stand von `src/`, `evals/`, `tests/` und `docs/` weicht nicht von diesem Commit ab. Trotzdem wird der damalige Lauf nicht als „sauberer Checkout“ bezeichnet. Das beeinträchtigt die vollständige Code-Rekonstruktion, nicht die Lesbarkeit der gespeicherten Antworten und Werkzeugausgaben.

Die zunächst genannte Dauer von etwa 1 h 40 min passt nicht zum Archiv: Die gespeicherten Latenzen summieren sich auf 6307,57 s; hinzu kommen 900 s festgelegte Wartezeit. Der letzte Snapshot ist von 10:43:22 UTC, danach folgen seriell aufgezeichnete Latenzen von 1499,22 s. `runs.json` wurde um 11:08:21 UTC geschrieben. Damit liegt der Zeitraum bei ungefähr **09:08–11:08 UTC, also 11:08–13:08 Uhr in Berlin: rund zwei Stunden**. Die Dateizeit allein wäre kein vollständiger Laufzeitnachweis; hier stimmen Zeitfenster, Latenzsumme und Dateizeit überein. Der ursprüngliche Log wurde für diese Auswertung nicht verwendet.

Die berechneten Kosten aller 60 Läufe einschließlich explorativer Antworten summieren sich auf **5,06212 USD**. Es handelt sich um die aus Token-Nutzung und konfigurierten Preisen berechnete Kostenmetrik.

## 7. Konsequenz für den Abschluss

Lauf 4 ist ausgewertet; sein negatives Funktionskriterium wird festgehalten. Die Prüfphase kann für diesen Prototyp mit dieser Einschränkung abgeschlossen werden. Ein weiterer bezahlter Lauf ist dafür nicht erforderlich.

Falls eine weitere Diagnoseverbesserung beauftragt wird, wäre der kleinste sinnvolle Schritt eine **Konsistenzprüfung zwischen Messpfadvertrauen, Gruppenbewertungen und alternativen Hypothesen**. Sie sollte Widersprüche zunächst sichtbar machen, statt automatisch die gewünschte Diagnose einzusetzen. Dazu gehören eine klare Bedeutung von Produktdefekt gegenüber Stationssensorfehler und die getrennte Behandlung eines unzuverlässigen Messwerts. Nach jeder solchen Änderung wären neue Ergebnisse als eigener Versuch zu kennzeichnen.

Ein Re-Test derselben Einheit ist eine getrennte spätere Erweiterung. Er behebt die hier beobachtete Reportinkonsistenz nicht automatisch.
