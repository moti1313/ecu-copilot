---
doc_id: TS-DCU-EOL
title: End-of-Line Test Specification – Door Control Unit DCU-A1 / DCU-B2
revision: D
date: 2026-05-12
owner: Electronics Test Engineering
---

# TS-DCU-EOL – End-of-Line Test Specification, Door Control Unit DCU-A1 / DCU-B2

## 1. Scope

This specification defines the end-of-line (EOL) test of the door control unit variants DCU-A1 (variant A, basic door control) and DCU-B2 (variant B, with keyless-entry antenna pre-processing). It applies to all EOL stations of the electronics production line (EOL-1, EOL-2, EOL-3). The test is a 100 % test: every unit is tested before packaging.

## 2. Test stations and variants

| Station | Name | Variants tested |
|---|---|---|
| 1 | EOL-1 (line A) | DCU-A1 |
| 2 | EOL-2 (mixed) | DCU-A1, DCU-B2 |
| 3 | EOL-3 (line B) | DCU-B2 |

All stations use the same test sequence and the same limit table (section 5). Station firmware release 3.4 or later is required.

## 3. Test sequence

The tests run in the following fixed order. The first failing test stops the sequence and determines the failure code.

1. LIN communication check (section 4.1) – failure code **E-120**
2. Firmware flash and verify (section 4.5) – failure code **E-401**
3. Quiescent (sleep) current measurement (section 4.3) – failure code **E-204**
4. Operating current, window lift run (section 4.4) – failure code **E-205**
5. Acoustic test, window lift run (section 6) – failure code **E-310**

## 4. Test conditions and methods

### 4.1 LIN communication check
The station requests the unit identification via LIN diagnostic frame 0x3C within 500 ms after power-on. Three attempts are allowed. If no valid response is received, the result is FAIL with code E-120. Typical root causes: open solder joint at connector J3 (pins 5/6), damaged connector, missing termination (see FMEA-DCU-B2, item 7).

### 4.2 Environmental validity of a test
Measurements are only valid if the PCB temperature at the start of the quiescent current measurement is between **18 °C and 32 °C** (station temperature sensor, position T1). If the temperature is outside this window, the test result shall be recorded as **INVALID**, not as FAIL, and the unit shall be re-tested after the station has returned to the valid range. Reason: the quiescent current of the microcontroller and the driver IC rises strongly with temperature (see DS-MCU-XM32F7 section 7.3, DS-DRV-HB4821 section 5.2); a limit violation above 32 °C does not indicate a defective unit.

Note (Rev. D): Station firmware 3.4 does not evaluate the temperature window automatically. Until firmware 3.5 is released, the station operator is responsible for checking T1 when the E-204 rate rises (see WI-EOL-PSEUDO section 3).

### 4.3 Quiescent current
Supply 12.0 V ± 0.1 V, unit in sleep mode (LIN bus idle for ≥ 2 s), measurement after 5 s settling, averaging 200 ms. Limits per variant in section 5. Variant B has a higher limit because the keyless-entry antenna front-end remains in a periodic polling mode.

### 4.4 Operating current
Window lift motor run for 1.5 s at 12.0 V, nominal load fixture. Average current must be inside the window in section 5. Current above the window indicates a stalled motor, short circuit or H-bridge fault; below the window indicates an open motor circuit.

### 4.5 Firmware flash and verify
Application firmware is flashed over LIN (variant A) or over the high-speed service interface (variant B, larger image). Flash + verify time is limited per variant in section 5. A timeout is reported as E-401.

## 5. Limit table

| Parameter | DCU-A1 (variant A) | DCU-B2 (variant B) | Failure code |
|---|---|---|---|
| LIN communication | response required | response required | E-120 |
| Flash + verify time | ≤ 45 s | ≤ 60 s | E-401 |
| Quiescent current (12 V, sleep) | ≤ 350 µA | ≤ 450 µA | E-204 |
| Operating current (window lift run) | 1.0 A … 2.4 A | 1.0 A … 2.4 A | E-205 |
| Acoustic score | ≥ 70 | ≥ 70 | E-310 |

Typical values at 25 °C: quiescent current DCU-A1 approx. 240 µA, DCU-B2 approx. 330 µA; flash time DCU-A1 approx. 31 s, DCU-B2 approx. 44 s.

## 6. Acoustic test

### 6.1 Test conditions
The acoustic test is performed in the sound-damped cell of the station. The test is only valid if the background noise level measured by the cell reference microphone is **≤ 45 dB(A)** during the motor run. Above 45 dB(A), the acoustic score is not meaningful and the result shall be treated as INVALID (same handling as section 4.2). Typical sources of background noise: forklift traffic, compressed-air blow-off at neighbouring stations, open cell door.

### 6.2 Acoustic score
The acoustic classifier compares the motor run recording with the reference spectrum of the variant and returns a score from 0 to 100 (100 = identical to reference). A score below 70 indicates a gear or motor noise defect (regular clicking or grinding). Background noise typically produces irregular, broadband interference and lowers the score without any defect of the unit.

## 7. Failure codes

| Code | Meaning | First check |
|---|---|---|
| E-120 | No LIN communication | Connector J3, solder joints pins 5/6, lot history |
| E-204 | Quiescent current above limit | Station temperature T1 (section 4.2), then unit |
| E-205 | Operating current outside window | Motor fixture, H-bridge driver |
| E-310 | Acoustic score below 70 | Cell background noise (section 6.1), then gear |
| E-401 | Flash/verify timeout | Service interface cable, firmware image |

## 8. Retest and escalation

A unit that fails may be retested once. If the second test fails as well, the unit is blocked and goes to failure analysis. If the failure rate of a station exceeds **5 % over 10 minutes** or **3 % over one shift**, the line lead shall be informed and WI-EOL-PSEUDO shall be applied before any unit is blocked.
