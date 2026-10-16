# Live-Prüfliste

Die Oberfläche zeigt drei parallele Prüfstationen und deren zuletzt abgeschlossene Einheiten. Sie nutzt ausschließlich bestehende Lesezugriffe auf `/results`, `/events`, `/faults` und die bisherigen Statistik-Endpunkte. Simulator, Agent und Benchmark werden dafür nicht geändert.

## Bedienung

- **Prüfung ansehen:** öffnet eine feste Kopie des Einzelbefunds mit Serial, Los, Variante, Zeit und Stationsurteil. Neue Prüfungen ändern diesen geöffneten Befund nicht.
- **Prüfablauf:** wird aus dem gespeicherten ersten Fehlercode und der Reihenfolge in TS-DCU-EOL §3 rekonstruiert. Nachfolgende Schritte heißen „nicht bewertet“. Es werden keine laufenden Prüfschritte oder Fortschrittszeiten erfunden.
- **Prüfvorgabe:** zeigt den betreffenden Abschnitt der synthetischen Spezifikation mit Revision.
- **Diese Prüfung untersuchen:** bereitet eine Frage mit den beobachteten Identifikatoren und dem Stationsurteil vor. Der Modellaufruf erfolgt erst nach „Frage untersuchen“. Die konkrete Einheit muss der Agent über seine Werkzeuge wiederfinden; anderenfalls soll er das ausdrücklich benennen.
- **Letzter Fehler:** öffnet den jüngsten fehlgeschlagenen Befund aus dem geladenen Verlauf, auch wenn die letzte Prüfung bestanden wurde.
- **Prüfliste pausieren:** hält nur die sichtbaren Einheiten und den Listenstand an. Twin und Datenerfassung laufen weiter. Fortsetzen zeigt den aktuellen Stand.

## Herkunft und Grenzen

1. **Demo-Störung / Betreiberwissen:** zeigt aktive Einstellungen und deren modellierte Wirkung. Diese Daten werden nicht in die vorbereitete Copilot-Frage übernommen. Die Agentenwerkzeuge bleiben unverändert und besitzen keinen Zugriff auf `/faults`.
2. **Beobachtete Prüfungen:** stammen aus dem Twin. SSE liefert neue Ergebnisse; regelmäßige Abfragen gleichen die letzten 90 Ergebnisse ab. Im Browser bleiben höchstens 120 Befunde, die Liste zeigt höchstens 24. Bei Verbindungsproblemen wird der alte Stand gekennzeichnet.
3. **Hypothese des Copilots:** bleibt eine Modellbewertung. Eine Seriennummer wird nur bei ausdrücklicher Nennung in einem Live-Beleg verlinkt; Aggregatbelege werden nicht einer beliebigen ECU zugeordnet. Eine vorbereitete Einzelprüfung ist noch kein Nachweis, dass der Agent diese Einheit abgerufen hat.

Ein „PASS“ ist das rohe Stationsurteil, keine pauschale Bauteilfreigabe. Ungültige Prüfbedingungen und ein zusätzlicher Defekt können gleichzeitig vorliegen. Eine Wiederholungsprüfung wird in dieser Oberfläche weder ausgeführt noch als bestätigt dargestellt.

## Spezifikationsreferenz aktualisieren

Die HTML-Datei enthält eine generierte Lesekopie der Spezifikation und ihrer Abschnitte, damit die Vorgaben ohne zusätzliche Server-Endpunkte geöffnet werden können. Nach Änderungen an den Quellen:

```bash
python scripts/update_ui_reference.py
```

`tests/test_production_reference.py` prüft die Übereinstimmung mit `docs/spec/TS-DCU-EOL.json` und den verwendeten Abschnitten aus `docs/TS-DCU-EOL.md`.
