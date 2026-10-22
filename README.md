# ECU Copilot

An investigation assistant for electronics end-of-line test engineers. A single agent combines
engineering tools and document retrieval to prepare structured assessments with traceable evidence.
All test data, specifications and component documents are synthetic. No production line is connected.

## Problem and approach

A failed test does not identify whether the cause is the unit, the test conditions, the measurement
path or several concurrent causes. The engineer needs test data and the applicable technical rules.
The copilot retrieves that context, calls analysis tools and proposes counter-checks. A verifier
checks references and flags selected unsupported or conflicting assessments. The engineer reviews
the report; recording a decision does not block, release or re-test a physical unit.

Explicit calculations and criteria are implemented in Python. The model selects tools and explains
their results. Invalid test conditions do not prove that a unit is healthy; a matching source does
not prove a diagnosis. Reducing investigation and documentation time is a hypothesis to be tested
with engineers, not an established economic benefit.

## Architecture and documentation

![Runtime architecture](design/presentation/diagrams/03-laufzeitarchitektur.svg)

- [Implemented architecture and data flow](design/ARCHITECTURE_CURRENT.md) (German).
- [Scope, method and limitations](design/CONCEPT.md).
- [Measured results](design/RESULTS.md) and [detailed run-4 error analysis](design/RUN4_REVIEW.md).
- [Technical slides](design/presentation/ECU-Copilot-Praesentation.pdf) and [diagrams](design/presentation/README.md).
- [References](design/presentation/RECHERCHE.md).

The Twin and Copilot are FastAPI services; Jaeger provides local tracing. Engineering functions,
retrieval and verification run inside the Copilot process. BM25 search is local; hybrid retrieval
adds local embeddings and embedded Chroma. Selected document passages, tool descriptions and
outputs are sent to the configured external model provider.

## Quick start

Requires Docker Compose and a model-provider API key for investigations.

```bash
cp .env.example .env
# Edit .env: choose LLM_PROVIDER and set the corresponding API key.
docker compose up --build
```

- Dashboard: http://localhost:8000
- Twin API: http://localhost:8001/docs
- Traces: http://localhost:16686

OpenAI (`LLM_PROVIDER=openai`) produced the published benchmark results. An Anthropic adapter is
also implemented. Hybrid retrieval downloads an embedding model on first use.

For local development with Python 3.12+ and uv:

```bash
uv sync --frozen
uv run python -m ecu_copilot.rag.ingest
uv run uvicorn ecu_copilot.twin.api:app --port 8001
# In another terminal:
uv run uvicorn ecu_copilot.copilot.api:app --port 8000
```

### First investigation

Without an API key the stack still starts: the dashboard shows the three stations and their live
tests, faults can be injected, and the offline tests run. Only `/ask` needs a model key.

1. Open the dashboard at http://localhost:8000 and let the simulator run for a minute.
2. In the panel *Demo-Störung · Betreiberwissen* inject a temperature drift on station 2 (default +10 °C).
   The agent has no tool for this panel; it has to infer the fault from measurements.
3. Wait two to three minutes. Variant B on station 2 starts failing with E-204 (quiescent current),
   variant A barely, because B sits closer to its limit.
4. Ask, for example: *Why does variant B on station 2 fail more often since a few minutes? Unit defect
   or test conditions?* The completed report includes the tool-call log; a model answer can take one to three minutes with gpt-5.
5. Read the report: one assessment per group (test validity separate from unit-defect indication),
   consistency marks if any, evidence with provenance ✓/✗, and a proposed counter-check. Expected for
   this fault: *test invalid (temperature), unit not assessable, cause station temperature*. An invalid
   test leaves the unit condition open; it does not clear the unit.
6. Open the same question as a trace in Jaeger (http://localhost:16686): one span per model call and
   per tool call. Reset the faults in the dashboard afterwards.

A second scenario: reset, inject a bad connector lot, ask about the E-120 failures on variant B. Here
the agent has to find a real defect concentrated in one lot rather than an environmental cause.

## Results and limitations

Run 4 used four regular scenarios, three repetitions per system and a shared frozen snapshot per
scenario. Exact means all expected group assessments are present with no additional causal assessment.

| System | Exact group assessments |
|---|---:|
| B0: rule engine | **12/12** |
| V2: agent with engineering tools | 8/12 |
| V1S: base tools, same report format | 5/12 |
| B1: single-call RAG, older format | 0/12 |

B1 lacks group assessments, so its score is not a general content-accuracy measure. V2 identified
the sensor hypothesis in S05 but also asserted a competing temperature cause in the final report.
Its live references resolved in 155/165 cases and document references in 47/47; this verifies
references, not diagnostic truth. The later consistency checker flags these issues without changing
the reports or the original 8/12 result. A separate archive-based trial of one model revision driven by
those flags did not repair the S05 reports (0/3) and left eight correct control reports unchanged (8/8);
no revision loop is part of the agent. No diagnostic advantage over rules was demonstrated on these
known patterns. Engineer time savings and performance on production data remain unmeasured.

## Scope of the local demo

This is a single-host engineering demonstrator, not a shared service.

- **Remaining limits before shared deployment:** optional shared API keys provide no user identity or roles;
  reads and Twin CORS remain open. Ports bind to localhost by default. Trace content may contain prompts and
  answers and needs redaction, access control and retention rules for real data. Investigation records survive
  restarts and tolerate damaged lines; corrupted decision logs still require recovery. These operational
  improvements do not change the recorded benchmark results.

## Offline checks

```bash
uv run ruff check .
uv run ruff format --check .
PYTHONPATH= RAG_MODE=bm25 uv run pytest
```

Offline tests use mocked model clients. Five archive-dependent tests skip when their original run archives are absent. This repository
includes published result documents, not the raw benchmark archives. Paid evaluations require an API key and an explicit command, for example:

```bash
uv run python evals/bench.py --scenarios S01,S04,S05,S08 --systems b0,v2 --repeats 3
```

A fresh evaluation may differ from the recorded run. Normal live investigations query the evolving
simulator per tool call; only the benchmark freezes its input. Re-testing the same identified unit and
a real MES adapter are future work. Jev is a separate shadow adapter and is not part of the normal
answer path. `evals/revision_trial.py` is an archive-based experiment on one targeted report revision;
it defaults to a dry run and is not part of the answer path either (see CONCEPT.md §13).

## Monitoring

Per question the Copilot records latency, model calls, tools, tokens, calculated cost and errors
(`data/metrics.jsonl`, summarised at `/metrics`). The same figures are exposed for Prometheus at
`/metrics/prometheus` (counters, a latency histogram, Twin and index gauges; no client library).
Traces per model call and tool call stay in Jaeger. An optional overlay adds Prometheus and Grafana
with a provisioned dashboard:

```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
# Prometheus http://localhost:9090 · Grafana http://localhost:3000 (anonymous viewer)
# ports taken by another stack: PROMETHEUS_PORT=9091 GRAFANA_PORT=3001 docker compose ... up -d
```

The dashboard answers operational questions over time: how long answers take (mean and rolling p95),
how many fail, how tokens and calculated cost develop, which tools are used, and whether Twin and
document index are up. Operational metrics do not establish diagnosis correctness; that requires separate evaluation
against known outcomes or an appropriate engineering counter-check.

## CI, release and deploy

Every push runs `.github/workflows/ci.yml`: `ruff check`, `ruff format --check`, the offline tests
(`RAG_MODE=bm25`, mocked model clients), then a Docker smoke test that builds the image, starts Twin and
Copilot with Compose and checks `/health` (Twin reachable, index ready), `/health/ready` and `/health/live`. The paid `eval` job runs only on
manual dispatch. Green CI proves that the software builds and its deterministic parts behave as tested;
it does not prove a correct diagnosis (see the S05 case in the results).

A Git tag `v*` runs `.github/workflows/release.yml`: it builds one versioned image (Twin and Copilot share
it), smoke-tests exactly that image and publishes it to GHCR as `ghcr.io/moti1313/ecu-copilot:<tag>`.
The initial public source repository does not imply that a matching public image is already
available. Build locally for the quick start above. After a release has successfully published its
image, deployment is a deliberate step on the target host:

```bash
export ECU_IMAGE=ghcr.io/moti1313/ecu-copilot
export ECU_VERSION=v0.3.0                 # example: use a tag that has actually been published
docker compose -f docker-compose.yml -f docker-compose.release.yml pull
docker compose -f docker-compose.yml -f docker-compose.release.yml up -d --no-build
curl -s localhost:8000/health
```

Rollback: set `ECU_VERSION` to the previous tag and repeat pull and up; the data volume is kept.
A Kubernetes deployment is future work. It would use `/health/live` for liveness and `/health/ready`
for readiness (503 when the Twin or index is unavailable). `/health` remains HTTP 200 for compatibility.

## Hardening update · 22 October 2026

The reviewed update adds restart-safe investigation records, separate liveness and readiness endpoints,
localhost port bindings, optional API keys per service, explicit model timeouts and retries, and operational
quality metrics with seven Prometheus alert rules. Retrieved passages carry visible prompt-injection
warnings; these are screening hints, not proof of resistance to attacks.

The benchmark scorer now handles multiple causes in the same scope. S02, S06 and S09 extend the synthetic
scenarios. Re-scoring leaves run 4 unchanged (B0 12/12, V2 8/12 exact); B0 misses the sensor fault in S06
when real heating occurs simultaneously. Whether the agent improves on that remains untested.

The dependency audit and image scan are reporting checks with downloadable JSON artifacts, not security
gates. Known findings and remaining work are recorded in [the roadmap](design/ROADMAP.md).

Optional `ECU_API_KEY` protects questions and decisions; `TWIN_API_KEY` protects simulated faults and reset.
Reads remain open. The dashboard keeps the two keys separately. The Docker healthcheck uses the compatible
`/health` route; it sets container health status and does not itself restart containers. Model timeouts apply
to individual calls, not the whole investigation.

## Layout

```text
src/ecu_copilot/  simulator, agent, tools, retrieval, verification and API
 docs/           synthetic engineering documents, BOM and machine-readable specification
 evals/          baselines, benchmark, scoring, scenarios, shadow experiment and revision trial
 tests/          offline unit and integration checks
 design/         architecture, results, scope and technical diagrams
```

## Development history and license

The technical development history has been retained and filtered to remove private planning and
preparation documents. Commit IDs differ from the original development history; historical benchmark
references remain as recorded. See [publication notes](PUBLICATION.md).

Additional historical technical notes are retained under `design/`; the implemented architecture and
recorded outcomes linked above describe the current prototype.

**Authorship and AI assistance.** The project was designed, decided and tested by Morteza Molaei. Two AI
coding assistants were used as pair programmers and reviewers, and this is stated openly: Claude Code
(Anthropic) wrote most of the code and documentation drafts under the author's direction and appears as
co-author in the commit trailers; OpenAI Codex acted as an independent reviewer, reproduced several of the
defects named in the result documents, and prepared this public copy of the repository. Where the documents
say "review" or "reviewer", that is one of these two assistants or a human colleague. Every benchmark
decision, every commit, the interpretation of the results and all paid model runs were the author's.

Licensed under the [MIT License](LICENSE).
