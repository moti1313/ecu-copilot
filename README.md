# ECU Copilot

An AI agent for test engineers on an electronics end-of-line (EOL) line, built as a prototype for a
production-grade LLM feature: **agent + tools + RAG**, with **tracing, cost accounting, guardrails and evals**
from day one. It runs against a **digital twin** of three EOL test stations for door control units
(DCU-A1 / DCU-B2), so the whole thing works on a laptop with `docker compose up`.

> **The story.** A test engineer sees that variant B started failing at station 2 ten minutes ago.
> Today: pull logs, search the test specification, ask a colleague, type an 8D report - two hours.
> With the copilot: one question. The agent reads the live data, compares it with the specification,
> recognises pseudo failures caused by temperature drift, and drafts the 8D report - with citations.
> And the monitoring shows what it cost and whether the answer was grounded.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  Browser: dashboard (live failure rates · fault injection · chat ·   │
│           tool trace · cost/latency KPIs)                            │
└───────────────┬─────────────────────────────────┬────────────────────┘
                │ REST                            │ REST
┌───────────────▼───────────────┐   ┌─────────────▼──────────────────┐
│  twin  (FastAPI, :8001)       │   │  copilot  (FastAPI, :8000)     │
│  digital twin of 3 EOL        │◄──│  Claude + SDK tool runner      │
│  stations, 2 variants         │   │  tools: search_docs (RAG)      │
│  · measurements, verdicts     │   │         get_station_stats      │
│  · fault injection: drift,    │   │         get_recent_results     │
│    hall noise, bad lot        │   │         lookup_part (BOM/PCN)  │
│  · SSE event stream           │   │         draft_8d_report        │
└───────────────────────────────┘   │  guardrails · cost log · evals │
                                    └─────────────┬──────────────────┘
┌───────────────────────────────┐                 │ OpenTelemetry (OTLP)
│  docs/  test spec, datasheets,│   ┌─────────────▼──────────────────┐
│  FMEA, PCN, work instruction  │   │  jaeger  (:16686)              │
│  → chunks → local embeddings  │   └────────────────────────────────┘
│  → ChromaDB + BM25 (hybrid)   │
└───────────────────────────────┘
```

| Concern | Choice | Why |
|---|---|---|
| Agent loop | Anthropic SDK tool runner (`@beta_tool`) | ~40 lines, every line explainable; no framework between us and the API. The same loop written by hand is in `examples/hello_agent.py`. |
| Model | `claude-opus-5-5` (agent), `claude-haiku-5-5` (eval judge) | adaptive thinking, strict tool schemas, prompt caching; a cheap judge for evals |
| Provider switch | `LLM_PROVIDER=openai` → `gpt-5` / `gpt-5-mini` through the same tools and prompt | the loop is written by hand on chat completions (`OpenAICopilot`); shows that the design is not tied to one vendor. Prompt caching and SDK-level spans exist only on the Anthropic path. |
| RAG | fastembed (multilingual MiniLM) + ChromaDB, fused with BM25 via RRF | embeddings for meaning (German questions over English docs), BM25 for exact tokens like `E-204`, `HB4821`; nothing leaves the machine except the question and the retrieved chunks |
| Twin | FastAPI, in-memory, seeded RNG | deterministic enough to test, realistic enough to tell the story; replaceable by a real MES/test system behind the same REST contract |
| Observability | OpenTelemetry → Jaeger; per-question JSONL metrics | the SDK emits spans on its own; one container for the UI; cost/latency/cache/citation KPIs without a SaaS |
| Quality | pytest (no API key) + golden-set evals (tools → facts → LLM judge) | regressions in prompt or model are caught by a number, not by a feeling |

## Quick start

```bash
cp .env.example .env            # put your ANTHROPIC_API_KEY in .env
docker compose up --build       # first start downloads the embedding model (~250 MB) into a volume
```

- Dashboard: http://localhost:8000 · twin API docs: http://localhost:8001/docs · traces: http://localhost:16686

Local development without Docker:

```bash
uv sync
uv run python -m ecu_copilot.rag.ingest                      # build the document index
uv run uvicorn ecu_copilot.twin.api:app --port 8001          # terminal 1
uv run uvicorn ecu_copilot.copilot.api:app --port 8000       # terminal 2 (needs ANTHROPIC_API_KEY)
```

Try it: click **Temperaturdrift St. 2**, wait a minute, ask
*"Warum fällt Variante B an Station 2 seit 10 Minuten überdurchschnittlich oft durch?"*

## Tests and evals

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest                        # no API key, no model download (RAG_MODE=bm25 in CI)
# If a ROS 2 workspace is sourced in your shell, its pytest plugins break collection: PYTHONPATH= uv run pytest
uv run python evals/run.py           # golden set against the live agent; needs twin running + API key
uv run python evals/run.py --only live-drift-pseudo-failure --no-judge
```

The eval has three layers per case - expected tools called (deterministic), key facts present
(deterministic), rubric satisfied (LLM-as-judge). It exits non-zero below `EVAL_MIN_PASS` (0.8),
which is the gate in the manual `eval` job of `.gitlab-ci.yml` / GitHub Actions.

## V2: deterministic evidence, verified, benchmarked

The literature on LLM agents for root-cause analysis is consistent on one point: the most frequent
failure is a coherent story the data does not support, and prompting does not fix it - checking does
(see `design/RESEARCH.md`). V2 therefore adds three things in front of and behind the model:

1. **Engineering layer** (`src/ecu_copilot/engineering/`, no LLM): `check_validity` (which FAIL verdicts
   are INVALID per the machine-readable spec `docs/spec/TS-DCU-EOL.json`, consistency-tested against the
   markdown), `detect_change` (change-point scan: onset, levels, z), `cluster_failures` (lot / firmware /
   station concentration with exposure-aware lift, rate ratio and z), `describe_signal` (descriptors,
   Iq-T1 relation incl. the sensor-fault signature). The agent is told to call these before it claims
   anything about validity, trends or lots - it integrates and explains, it does not compute.
2. **Report schema V2**: `assessments` per affected group with *test validity* separate from *defect
   indication* (an invalid test says nothing about the unit; concurrent causes are two entries),
   hypotheses with a *discriminating* test, evidence items with a structured `ref` (tool call, field,
   station, variant, window, value / doc, revision, section).
3. **Verification** (`copilot/verify.py`, no LLM): *provenance* - does the ref resolve to this run's tool
   output for exactly that scope and value, does the cited document / section / revision exist; and
   *support* - spec comparisons for live refs, keyword overlap for documents (a heuristic, named as such).
   The UI shows both marks per evidence item.

`AGENT_PROFILE=v1|v2` keeps the original agent available for comparison. The **benchmark**
(`evals/bench.py`) runs scenarios with known truth (`evals/scenarios/`) against four systems - **B0** a
fair rule engine on the same engineering tools, **B1** single-call RAG without tools, **V1**, **V2** -
with repeats, a solvability check per scenario, and the metrics from `design/CONCEPT.md` §5. Results are
appended to `design/RESULTS.md`.

```bash
uv run python evals/bench.py --scenarios S01,S08 --systems b0,b1,v1,v2 --repeats 3
```

## The investigation workspace

The agent's final message is a structured **investigation report** (JSON schema enforced on both
providers): finding type, hypotheses with *evidence strength* (strong / moderate / weak / rejected -
never a made-up confidence number), evidence items with source (`live` tool data or `document`
citation), the proposed next test, and the affected components. The dashboard renders it as:

- a **signal strip** (I_q and T1 over time, limit line, invalid-temperature band, fail markers, cursor),
- a **schematic** of the door drive with the fault path per failure code and clickable parts (BOM / PCN),
- the **agent's activity** (every tool call with arguments, duration and what came back),
- hypotheses, evidence table, next test - and **approval by the engineer**, logged with the trace id
  (`POST /decisions`).

All test data comes from the digital twin and the documents are synthetic; the UI says so.

## How the demo scenario works

1. The station firmware checks limits from the test specification, but **not** the spec's environmental
   validity rule (TS-DCU-EOL §4.2: results outside 18-32 °C are INVALID, not FAIL). That gap exists in the
   twin on purpose - it mirrors a real Rev. D note in the spec.
2. Quiescent current rises with temperature (~3 %/K). Variant B sits closer to its limit (330 µA typical
   vs 450 µA limit) than variant A (240 vs 350), so drift hits B first.
3. The agent sees E-204 rising on station 2 / variant B, reads the mean temperature (>32 °C), finds §4.2
   and FMEA item 11, and concludes *pseudo failure: fix the station, re-test, do not block units*.

Two more faults are built in: hall noise (E-310 above 45 dB(A), spec §6.1) and a bad connector lot
(E-120 clustered on lot L2439-07, FMEA item 7) - a *real* failure the agent must not explain away.

## Production notes (what would change at a real site)

- **Data sources:** the twin becomes an adapter to the MES / test-station database; the five tools keep their
  schema. Events would come from Kafka instead of SSE.
- **Deployment:** the compose file maps 1:1 to two Deployments, a Service each, a Secret for the key and an
  OTLP collector; the embedding model lives in an image layer or a PVC.
- **Model access:** `AnthropicBedrockMantle` swaps in for `Anthropic()` on AWS; nothing else changes.
- **Guardrails:** the citation check is a minimum. Next: a topic classifier on input, schema-validated
  answers for the 8D path, and sampling of answers into the eval set from the metrics log.
- **Prompt caching:** the system prompt is cached (`cache_control`), the dashboard shows the cache hit ratio.

## Repository layout

```
src/ecu_copilot/
  config.py            environment-driven settings, pricing table
  twin/                models.py (API contract) · simulator.py (the generator) · api.py (FastAPI)
  rag/                 chunking.py · index.py (Chroma + BM25, RRF) · ingest.py (CLI)
  copilot/             tools.py · agent.py · api.py · telemetry.py · metrics.py · static/index.html
docs/                  six engineering documents (synthetic, consistent limits) + BOM-DCU.json
evals/                 golden.json · run.py
tests/                 25 tests, fake LLM client
examples/hello_agent.py   the agent loop written by hand (day-1 version)
```
