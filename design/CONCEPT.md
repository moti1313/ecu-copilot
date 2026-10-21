# ECU Copilot: scope and evaluation method

Technical summary for this public repository. Published outcomes are in [RESULTS.md](RESULTS.md)
and [RUN4_REVIEW.md](RUN4_REVIEW.md); the implemented runtime is in [ARCHITECTURE_CURRENT.md](ARCHITECTURE_CURRENT.md).

## 1. Problem and intended benefit

Investigate whether a failed EOL test is related to the unit, test conditions, measurement path or
concurrent causes. Combine data and technical specifications into an inspectable report. Reducing
investigation preparation and documentation time while preserving decision quality is an unmeasured
hypothesis. The workflow has not been validated against a specific production site's practices.

## 2. Architecture

One agent selects local tools and receives their outputs through an external model API. Python
functions implement validity checks, change detection, exposure-aware failure clustering and signal
descriptors. Retrieval supplies document passages. Structured assessments separate test validity
from indications of a unit defect.

## 3. User workflow

Open a completed test, formulate an investigation, inspect group assessments and their evidence,
review proposed counter-checks, and record a decision. Recording is not an actuator command.

## 4. Data and scenarios

A seeded stateful simulator generates synthetic tests on three parallel stations. Fault injection
includes temperature drift, background noise, connector-lot faults and a temperature-sensor offset.
The agent has no fault-injection tool. Scenario definitions specify scope, expected assessments,
waiting periods and solvability checks. They are evaluation inputs, not production evidence.

## 5. Baselines and metrics

B0 uses fixed rules on the engineering functions. B1 is single-call RAG with the older output format.
V1S has base tools and the V2 report format; V2 adds engineering tools. A scenario snapshot is shared
by all systems and repetitions. Measure exact group assessments, overall finding, additional claims,
reference provenance, tool use, abstention, latency and calculated token cost. Three repetitions on
one snapshot measure response variation, not three independent industrial cases. B1's older format
limits comparisons using assessment metrics.

## 6. Evidence

Tool references identify a call, scope, field and value. Document references identify a source,
revision and section. Matching provenance is distinct from statement support or causal correctness;
document support uses a keyword heuristic. An invalid test leaves the unit condition open.

## 7. Extensions

Persistent same-unit re-testing, automatic hypothesis counter-checking and real-system integration
are future work. They are not implemented capabilities of this prototype.

## 8. Practical validation

A future engineer study should compare existing tools and copilot-assisted work on comparable
historical cases. Measure total time, review and documentation effort, quality of the next action,
incorrect conclusions and unnecessary tests. Consider integration, operation and maintenance costs.
Freed time initially represents capacity rather than guaranteed cash savings.

## 9. Experiment separation

Keep rule changes, prompt changes and alternative-model experiments distinguishable. Preserve
original outcomes and report limitations. A new experiment does not retroactively improve an old score.

## 10. Run 4

Recorded configuration: gpt-5, medium effort, 24,000-token limit and prompt 2026-10-16.3. Four regular
scenarios (S01, S04, S05, S08), three repetitions and four systems yield 48 regular runs; S08w supplies
12 separate exploratory runs. The prior functional criterion required V2 to match or exceed B0 on
S04/S05 exact assessments and to avoid extra causal assessments in at least two S01 repetitions.
It was not met: B0 12/12, V2 8/12, V1S 5/12, B1 0/12. The archive records a dirty working tree and no
complete historical diff; exact code reconstruction is limited. This repository does not contain
the original raw archives. Details and error analysis are retained in the result documents.

## 11. Consistency checker

Deterministic marks, not automatic corrections:

- K0: required sensor-plausibility coverage is missing or empty.
- K1: temperature-based invalidity is asserted while the same measurement path is in doubt.
- K2: a station cause and unit-defect indication need separate justification.
- K3: competing assessments in an identical scope need separate justification.
- K4: the relevant cross-station comparison of a connector lot is missing.

Known limits include no direct assessment-to-evidence linkage, incomplete handling of overlapping
scopes and time windows, and no independent reference temperature source. Sensor faults and actual
heating may coexist. Replay marks S05/V2 with K1/K2/K3 and S08/V2 with K4 in all three repetitions.
It changes neither the report nor the original score. Synthetic counter-examples are in the tests.

## 12. Jev shadow experiment

Separate adapter, never part of the normal answer path. Pinned model jev-1.13.0 received prepared
engineering outputs and specification excerpts from 15 saved V2 development runs, without V2's
conclusions or the hidden fault configuration. Context was not byte-identical to V2's. Questions
separately cover next counter-check, unreliable T1 and additional systematic product cause.

Recorded result: next check 12/15 against the predefined expectation, the other two questions 15/15
each; the fixed comparison rule scored 15/15. Calculated cost 0.006 USD, mean latency 342 ms. These
are development cases, not held-out validation or proof of calibration. No integration followed.
`evals/jev_shadow.py` defaults to dry run; sending requires `--send` and a separately configured key.

## 13. Targeted revision: one archive-based trial

One revision triggered by the K1 mark, with feedback generated from the marks, no tools, the same frozen
tool outputs numbered as stored, explicit budgets (one call, 24,000 tokens, 240 s, no SDK retries), both
reports kept, and improvements and regressions measured separately with the benchmark scorer. Cases: the
three S05/V2 reports carrying K1 and eight originally correct V2 reports as controls (S01, S04, S08).

Recorded result (2026-10-20, gpt-5, 0.88 USD): K1 cases fixed 0/3; controls unchanged and correct 8/8;
no regressions, no truncated or failed calls. The success criterion (at least 2/3 fixed and 8/8 controls)
was not met. In all three S05 cases the model removed the contradicted temperature assessment and kept
`unknown / suspected / sensor_t1`, so the station-sensor fault remained a unit-defect suspicion and the
overall finding changed from `mixed` to `real_failure`. The contradiction disappeared; the error changed
form. No revision loop is part of the agent. `evals/revision_trial.py` defaults to a dry run.
