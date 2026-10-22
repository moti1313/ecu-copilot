# Roadmap und Umsetzungsstand – Empfehlungen aus den Reviews (Stand 22.10.2026, Branch `hardening-2026-10-22`)

Quellen: externes Senior-Review (21.10.), DevOps/LLMOps-Empfehlungen (21.10.), Reviews von Codex und Kollegen (17.–21.10.).
Regel: Jede Zeile nennt, was umgesetzt ist, was bewusst offen bleibt und warum. Nichts hiervon verändert die
Ergebnisse von Lauf 4 oder der beiden verworfenen Versuche (Jev, Überarbeitung). Die geprüften Änderungen dieses Branches wurden am 22.10.2026 zur Veröffentlichung freigegeben.
Die historischen Versuchsergebnisse bleiben unverändert.

## Umgesetzt auf diesem Branch (offline prüfbar, keine Modellaufrufe)

| Bereich | Umsetzung | Nachweis |
|---|---|---|
| Persistenz | Zuordnung Untersuchung → Entscheidung wird beim Start aus `investigations.jsonl` geladen und bei Fehltreffer nachgelesen; kein 404 nach Neustart; abgeschnittene oder beschädigte Zeilen werden übersprungen, gemeldet und in `/health` gezählt | `tests/test_phase0.py::test_decision_survives_restart_via_investigations_file` |
| Health | `/health/live` (Prozess lebt) und `/health/ready` (503, wenn Twin nicht erreichbar oder Index nicht geladen) getrennt; `/health` bleibt 200 und meldet `ok`/`degraded` | `test_health_live_and_ready_semantics`; CI-Starttest prüft beide |
| Netz | Compose bindet Host-Ports standardmäßig an 127.0.0.1 (`BIND_ADDRESS` überschreibbar) | `docker compose config` |
| Zugriff | Optionale Schlüssel: `ECU_API_KEY` (POST /ask, /decisions), `TWIN_API_KEY` (Störungen, Reset); Header `X-API-Key`; Lesezugriffe offen; Dashboard hält je Dienst einen Schlüssel, sendet ihn nur an diesen Dienst, baut Header je Versuch neu und fragt bei 401 einmal nach | `tests/test_api_auth.py` (4), `tests/test_dashboard_js.py` (node) |
| Zuverlässigkeit | Modellclients mit Timeout 300 s und höchstens 1 Wiederholung statt SDK-Standard 600 s / 2 | `tests/test_client_limits.py` |
| Observability | Je Frage: Werkzeugfehler, Konsistenz-Marken je Code, unbelegte Herkunft, Injection-Treffer im Metrik-Log und in Prometheus; Alarmregeln (Scrape, Twin, Index, Fehlerquote, p95, Werkzeugfehler, Kosten) mit `promtool` geprüft | `tests/test_prometheus.py`, `monitoring/alerts.yml` |
| Trace-ID | war bereits durchgängig: `trace_id` in Untersuchung, Entscheidung, Metrik-Log; Jaeger-Link im Dashboard | `copilot/api.py`, `metrics.py` |
| CI | Job `security`: Abhängigkeits-Audit (pip-audit auf dem Lock-Export) und Image-Scan (Trivy), zunächst **berichtend**, weil `pillow` 12.3 von `fastembed` 0.9 festgehalten wird und drei CVEs offen sind; Dependabot für Actions, uv, Docker | `.github/workflows/ci.yml`, `.github/dependabot.yml` |
| RAG | Retrieval-Evaluation: 20 Goldfragen → Abschnitte, `hit@k`, `recall@k`, MRR; BM25: MRR 0,85; englische Fragen 17/18 in den Top 5 (q16 fehlt); deutsche Fragen 1/2 in den Top 5 (q20 Rang 2, q19 ohne Treffer); Test mit Mindestschwelle. Hybrid noch nicht gemessen, daher keine Aussage über Embeddings | `evals/retrieval_eval.py`, `tests/test_retrieval_eval.py` |
| Sicherheit | Prompt-Injection-Screening auf Dokumenttreffern (markiert, blockiert nicht); Hinweis in Werkzeugzeile, Verifier-Zusammenfassung (`injection.flagged`) und Belegnotiz des Dashboards; gezählt je Frage und in Prometheus. Ein Regex-Screening ist ein Hinweisgeber, kein Nachweis von Robustheit | `rag/injection.py`, `tests/test_injection.py` |
| Benchmark-Scorer | Jede erwartete Bewertung wird genau einer Antwortbewertung zugeordnet (vorher: immer die erste im Geltungsbereich, bei zwei Ursachen im selben Geltungsbereich höchstens 1/2). Rescore aller Archive: Lauf 4 unverändert (B0 12/12, V2 8/12), S06/B0 bleibt 1/2 | `tests/test_bench.py::test_scorer_matches_two_causes_in_the_same_scope` |
| Konsistenz K1 | löst nicht aus, wenn `describe_signal` `iq_follows_t1` zeigt: der Strompfad stützt die Erwärmung unabhängig. Die S06-Musterlösung trägt damit keine Marke (K3 setzt einen Bauteilverdacht voraus, der dort fehlt); Replay von Lauf 4 unverändert | `tests/test_consistency.py` |
| Evaluation | Drei neue Szenarien als Gegenbeispiele: S02 Lärm, S06 Sensorfehler plus echte Erwärmung, S09 Lärm plus Los; Lösbarkeit nach einer Kalibrierungsrunde erfüllt; B0 kostenlos: S02 1/1, S09 2/2, **S06 1/2** (Regelwerk sieht den Sensor nicht, wenn echte Erwärmung die Entkopplung verdeckt) | `evals/scenarios/S02*, S06*, S09*`, RESULTS.md Einordnung 22.10. |

## Bewusst offen, mit Grund

| Empfehlung | Entscheidung | Grund |
|---|---|---|
| Scans als harte CI-Blocker | nach Triage | Hinweis: `continue-on-error` toleriert auch Scanner-Ausfälle, ein grüner Job ist keine Sicherheitsfreigabe; seit 22.10. liegen Audit und Scan als JSON-Artefakte (30 Tage) am Lauf.  Stand des ersten Laufs (22.10., Branch-CI): **pip-audit** 29 Hinweise in 2 Paketen: `pillow` 12.3.0 (24 CVEs, Fix 13.0.0, wird von `fastembed` 0.9 festgehalten) und `chromadb` 1.5.9 (PYSEC-2026-311, -3813, -3814, -3815, keine Fix-Version in der aktuellen Auflösung); `certifi` wurde gehoben. **Trivy:** Betriebssystem des Images (Debian 13.7) 0 Treffer, Python-Pakete 8 (6 HIGH, 2 CRITICAL), im Wesentlichen dieselben `pillow`-Einträge. Nächste Schritte: `fastembed` auf eine Version mit `pillow` ≥ 13 heben und die Hybrid-Suche danach erneut messen; `chromadb` beobachten (Dependabot); dann `continue-on-error` entfernen und begründete Ausnahmen in einer `.trivyignore` führen. |
| Benchmark der neuen Szenarien mit V2 (bezahlt) | nach Freigabe, eigene Festlegung wie §10 | Kosten und Vorab-Festlegung; B0 läuft kostenlos vorab |
| Verifier: Zeitfenster, verschachtelte Geltungsbereiche, Evidence Coverage je Bewertung | eigener Versuch | braucht Belegzuordnung je Bewertung (Schemaänderung, §11 Grenzen) |
| Überarbeitungsschleife b2 (Rückmeldung je Marke) | eigener Versuch, §13 | Stufe b verfehlt; neue Rückmeldung muss vorab festgelegt werden |
| Hybrid-Retrieval-Evaluation, Reranking | nach Messung | erst MRR hybrid gegen BM25 auf demselben Goldstandard messen, dann Reranking |
| Human-Feedback-Erfassung, Zeitvergleich mit Prüfingenieuren | braucht Prüfingenieure | wirtschaftlicher Nachweis, nicht per Benchmark |
| Auth als OIDC/RBAC, Redaction in Traces, Aufbewahrung | bei gemeinsamer Bereitstellung | optionaler Schlüssel ist Übergang, kein Identitätsmanagement |
| Staging-VM mit Terraform und Ansible, automatisches Deployment, Rollback-Test | wenn ein Zielsystem existiert | lokal nur Compose; Deploy bleibt bewusster Befehl |
| K3s, Helm, Argo CD (GitOps) | als Lernprojekt nach dem Gespräch | Playground-Wissen vorhanden; Nutzen erst bei mehr als einem Zielsystem |
| SBOM und signierte Images | mittel | sinnvoll, sobald jemand die Images konsumiert |
| Multi-Agent, Jenkins | nicht | kein Problem, das sie lösen; Jenkins nur als Vergleichsübung |
| Ende-zu-Ende-Zeitbudget je Untersuchung | offen | Client-Timeout begrenzt Einzelaufrufe, nicht bis zu zwölf Iterationen mit Retries; braucht Abbruchkette im Agenten |
| Benchmark-Snapshots versionieren | offen | liegen unter `data/` (git-ignoriert); für unabhängige Replays als private CI- oder Release-Artefakte sichern |
| Docker `HEALTHCHECK` | bleibt `/health` | prüft nur den Prozess; Bereitschaft (Twin, Index) ist Sache des Orchestrators über `/health/ready`, dokumentiert im README |
