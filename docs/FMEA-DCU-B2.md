---
doc_id: FMEA-DCU-B2
title: Process FMEA excerpt – Door Control Unit DCU-B2, SMT and EOL
revision: 7
date: 2026-03-20
owner: Quality Engineering Electronics
---

# FMEA-DCU-B2 – Process FMEA excerpt, DCU-B2 (SMT assembly and end-of-line test)

Rating scales: Severity S, Occurrence O, Detection D (1 = best, 10 = worst). RPN = S × O × D. Items with RPN ≥ 100 require an action plan.

## 1. Scope
Process steps covered in this excerpt: solder paste printing, reflow soldering, press-fit of connector J3, EOL test. Design FMEA items are referenced where relevant.

## 2. Item list

| Item | Process step | Failure mode | Potential effect | Potential cause | S | O | D | RPN | Detection at EOL |
|---|---|---|---|---|---|---|---|---|---|
| 3 | Reflow | Insufficient solder on LQFP-64 (XM32-F7) pins | Intermittent CPU function, no LIN response | Paste printing offset, stencil wear | 8 | 2 | 4 | 64 | E-120 |
| 5 | Reflow | Solder void under HB4821 exposed pad | Driver overheating, early thermal shutdown | Reflow profile, paste volume | 7 | 3 | 5 | 105 | Not detected at EOL (field risk) – action: X-ray sampling |
| 7 | Press-fit J3 | **Open or cracked solder joint / press-fit at connector J3 pins 5/6 (LIN)** | **No LIN communication, unit cannot be flashed or diagnosed** | **Connector lot with pin length out of tolerance; press-fit force out of window** | 9 | 2 | 3 | 54 | **E-120** |
| 9 | Reflow | Tombstoning of 0402 capacitors in antenna front-end (variant B only) | Keyless entry range reduced | Uneven pad heating | 6 | 3 | 6 | 108 | Not detected at EOL – action: AOI rule update |
| 11 | EOL test | Pseudo failure E-204 due to station temperature above 32 °C | Good units rejected, rework cost, line stop | Station heater, closed cell door, summer ambient, missing firmware check (TS-DCU-EOL 4.2) | 4 | 5 | 6 | 120 | Visible as rising mean T1 with rising E-204 share |
| 12 | EOL test | Pseudo failure E-310 due to background noise above 45 dB(A) | Good units rejected, rework cost | Forklift traffic, air blow-off at neighbouring station, cell door not closed | 4 | 4 | 5 | 80 | Visible as rising mean noise level with rising E-310 share |
| 14 | SMT | Wrong or counterfeit HB4821 after end of life | Driver failure in field | PCN-2026-017 not implemented, grey-market sourcing | 9 | 2 | 7 | 126 | Not detected at EOL – action: lot traceability, qualify HB4830 |

## 3. Notes on item 7 (connector J3)

A connector lot with pin length below the lower tolerance leads to a press-fit joint that passes the in-circuit test (contact under probe pressure) but opens under thermal cycling or already during handling. The failure appears as an E-120 cluster at EOL that is **lot-dependent**: failures concentrate on serial numbers of one connector lot while other lots on the same station are unaffected. Separation by lot is therefore the first analysis step for any E-120 increase (see WI-EOL-PSEUDO section 4).

## 4. Notes on items 11 and 12 (pseudo failures)

Both items describe failures of the test environment, not of the unit. Characteristic signature:
- Item 11: mean PCB temperature T1 of the station rises above 32 °C; E-204 share increases; variant B is affected first and more strongly because its nominal quiescent current (approx. 330 µA) is closer to its limit (450 µA) than variant A (approx. 240 µA versus 350 µA).
- Item 12: mean background noise rises above 45 dB(A); E-310 share increases on all variants of that station; neighbouring stations are unaffected unless they share the noise source.

In both cases units shall not be blocked; the station condition shall be corrected and the units re-tested.
