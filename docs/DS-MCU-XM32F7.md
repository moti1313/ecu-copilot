---
doc_id: DS-MCU-XM32F7
title: Datasheet excerpt – XM32-F7 automotive microcontroller
revision: 2.1
date: 2025-11-03
owner: Component Engineering (excerpt from supplier datasheet)
---

# DS-MCU-XM32F7 – XM32-F7 Automotive Microcontroller (datasheet excerpt)

## 1. Overview

The XM32-F7 is a 32-bit automotive microcontroller used as the main controller of the door control units DCU-A1 and DCU-B2. It integrates a LIN transceiver interface, 512 kB flash, 128 kB RAM and a low-power sleep mode with periodic wake-up.

## 2. Qualification

- Qualified to **AEC-Q100 Grade 1** (ambient operating temperature −40 °C to +125 °C).
- Package: LQFP-64, lead-free, moisture sensitivity level MSL 3.
- Functional safety: ASIL B capable (used as QM in DCU-A1, ASIL A in DCU-B2).

## 3. Absolute maximum ratings

| Parameter | Min | Max | Unit |
|---|---|---|---|
| Supply voltage VDD | −0.3 | 6.0 | V |
| Junction temperature TJ | −40 | 150 | °C |
| Storage temperature | −55 | 150 | °C |

## 4. Recommended operating conditions

| Parameter | Min | Typ | Max | Unit |
|---|---|---|---|---|
| Supply voltage VDD | 3.0 | 5.0 | 5.5 | V |
| Ambient temperature TA | −40 | 25 | 125 | °C |

## 5. Flash memory

- 512 kB program flash, 100,000 erase/write cycles, data retention 20 years at 85 °C.
- Programming time: typ. 45 µs per 64-byte row. A full 512 kB image programs in approx. 20 s plus verify.

## 6. Sleep mode

In sleep mode the CPU and peripherals are stopped; only the LIN wake-up detector and the low-power oscillator remain active. The device wakes on a LIN dominant pulse of ≥ 150 µs.

## 7. Electrical characteristics

### 7.1 Run mode current
| Condition | Typ | Max | Unit |
|---|---|---|---|
| 80 MHz, all peripherals on, 25 °C | 38 | 55 | mA |

### 7.2 Sleep mode current at 25 °C
| Condition | Typ | Max | Unit |
|---|---|---|---|
| Sleep, LIN wake-up detector on, VDD = 5 V, 25 °C | 45 | 80 | µA |

### 7.3 Sleep mode current versus temperature
The sleep current is dominated by transistor leakage and therefore increases exponentially with junction temperature. Typical values at VDD = 5 V:

| TJ | Typ sleep current | Relative to 25 °C |
|---|---|---|
| −40 °C | 12 µA | 0.27 |
| 25 °C | 45 µA | 1.00 |
| 45 °C | 92 µA | 2.0 |
| 65 °C | 190 µA | 4.2 |
| 85 °C | 400 µA | 8.9 |
| 125 °C | 1,600 µA | 36 |

Design note: between 25 °C and 65 °C the sleep current rises by approximately **3.5 % per kelvin** (doubling roughly every 20 K). System-level quiescent current limits must therefore be specified together with a measurement temperature window.

### 7.4 LIN interface
- Baud rate 19.2 kbit/s, LIN 2.2A compliant.
- Dominant pulse detection ≥ 150 µs; shorter pulses are filtered.

## 8. Ordering information

| Order code | Package | Temperature grade | Status |
|---|---|---|---|
| XM32F7-512-LQ64-G1 | LQFP-64 | Grade 1 | Active |
| XM32F7-512-LQ64-G2 | LQFP-64 | Grade 2 (−40 … +105 °C) | Active |
