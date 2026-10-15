---
doc_id: WI-EOL-PSEUDO
title: Work instruction – Handling of rising failure rates and pseudo failures at EOL
revision: 3
date: 2026-06-02
owner: Production Engineering Electronics
---

# WI-EOL-PSEUDO – Handling of rising failure rates and pseudo failures at EOL stations

## 1. Purpose
This work instruction defines what to do when the failure rate of an EOL station rises, and how to distinguish a **pseudo failure** (the test environment is out of specification) from a **real failure** (the unit is defective). Blocking good units costs rework time and line capacity; shipping defective units is a field risk. Both must be avoided.

## 2. Definitions
- **Pseudo failure:** a FAIL verdict caused by the test environment (temperature, noise, fixture, cable) while the unit is within specification. Per TS-DCU-EOL sections 4.2 and 6.1 such results are INVALID.
- **Real failure:** a FAIL verdict reproducible under valid test conditions.
- **Escalation threshold:** failure rate above 5 % over 10 minutes or above 3 % over one shift on one station (TS-DCU-EOL section 8).

## 3. First checks by failure code (within 10 minutes)

| Code | Check first | Pseudo failure if … | Real failure if … |
|---|---|---|---|
| E-204 | Mean station temperature T1 over the last 10 minutes | T1 > 32 °C (or < 18 °C); rate rises with temperature; variant B affected first | T1 within 18–32 °C and failures spread over lots and variants |
| E-310 | Mean background noise at cell microphone | Noise > 45 dB(A); scores drop without pattern; neighbouring stations possibly affected | Noise ≤ 45 dB(A); affected units show regular clicking in the recording |
| E-120 | Distribution of failures by connector/PCB lot | Not applicable – E-120 is practically never environmental | Failures concentrate on one lot (FMEA-DCU-B2 item 7) or one station fixture |
| E-205 | Motor load fixture, fixture cable | Fixture or cable defect: all variants affected on one station | Single units, current far above window (stalled motor, driver fault) |
| E-401 | Service interface cable, flash image version | Cable or image: all units on the station affected | Single units |

## 4. Procedure

1. Confirm the rise: compare the failure rate of the last 10 minutes with the previous 30 minutes for the same station and variant.
2. Identify the dominant failure code.
3. Perform the first check from the table in section 3.
4. **Pseudo failure confirmed:** do not block the units. Correct the station condition (close cell door, switch off heater, stop air blow-off, wait for T1 to return to range). Re-test the affected units. Record the event in the station log.
5. **Real failure suspected:** block the affected units, separate by lot, inform the line lead, and open an 8D report (section 5) if more than 10 units are affected or the cause is a supplier lot.
6. Inform the line lead in both cases if the escalation threshold (section 2) was exceeded.

## 5. 8D report – minimum content

| Discipline | Content |
|---|---|
| D1 Team | Names and roles (test engineering, quality, production) |
| D2 Problem description | Station, variant, failure code, time window, failure rate before/after, number of affected units, lots |
| D3 Containment | Units blocked or re-tested; station condition corrected; customer impact |
| D4 Root cause | Confirmed cause with evidence (measurements, lot separation, documents referenced) |
| D5 Corrective action | Planned action, owner, due date |
| D6 Implementation | Verification that the action is effective (failure rate after action) |
| D7 Prevention | Changes to specification, FMEA, firmware, training |
| D8 Closure | Sign-off |

A draft 8D with D1 to D4 filled in shall be available within one shift of the escalation.

## 6. Typical mistakes
- Blocking units at the first rate increase without checking T1 or noise level.
- Re-testing immediately after the station condition was corrected – T1 needs 10 to 15 minutes to return to range.
- Mixing lots during re-test, which destroys the lot evidence needed for an 8D on E-120.
