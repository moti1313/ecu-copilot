---
doc_id: DS-DRV-HB4821
title: Datasheet excerpt – HB4821 H-bridge motor driver
revision: 1.4
date: 2024-08-19
owner: Component Engineering (excerpt from supplier datasheet)
---

# DS-DRV-HB4821 – HB4821 Integrated H-Bridge Motor Driver (datasheet excerpt)

## 1. Overview

The HB4821 is an integrated H-bridge driver for DC motors up to 8 A peak, used in DCU-A1 and DCU-B2 to drive the window lift motor. It integrates current sensing, over-current shutdown, thermal shutdown and a low-current sleep mode controlled by the SLEEP pin.

## 2. Qualification
- **AEC-Q100 Grade 1**, operating ambient −40 °C to +125 °C.
- Package: HTSSOP-28 with exposed pad, MSL 3.

## 3. Key parameters

| Parameter | Min | Typ | Max | Unit |
|---|---|---|---|---|
| Supply voltage VS | 5.5 | 13.5 | 28 | V |
| Continuous output current | – | – | 5.0 | A |
| Peak output current (< 1 s) | – | – | 8.0 | A |
| RDS(on) high side + low side, 25 °C | – | 55 | 75 | mΩ |
| Over-current shutdown threshold | 6.5 | 7.5 | 8.5 | A |

## 4. Protection

### 4.1 Over-current
If the output current exceeds the shutdown threshold for more than 20 µs, the bridge switches off and the FAULT pin is pulled low. A stalled motor at 12 V typically draws 6 to 9 A and triggers this protection. At the EOL test, a stalled or shorted motor is visible as an operating current far above the normal 1.0 to 2.4 A window before the protection engages.

### 4.2 Thermal shutdown
Thermal shutdown at TJ = 165 °C (typ.), hysteresis 20 K.

## 5. Sleep mode

### 5.1 Function
With SLEEP = low, the charge pump, gate drivers and current sense amplifier are switched off. Wake-up takes ≤ 500 µs.

### 5.2 Sleep current versus temperature
| TJ | Typ sleep current (VS = 12 V) | Max |
|---|---|---|
| 25 °C | 18 µA | 30 µA |
| 45 °C | 38 µA | 60 µA |
| 65 °C | 80 µA | 125 µA |
| 85 °C | 170 µA | 260 µA |

The sleep current roughly doubles every 20 K, in line with the microcontroller (DS-MCU-XM32F7 section 7.3). In the DCU design the HB4821 contributes approximately 20 to 25 µA of the total quiescent current at 25 °C.

## 6. Ordering information and lifecycle

| Order code | Package | Status |
|---|---|---|
| HB4821-QHTS28 | HTSSOP-28 | **End of life – see PCN-2026-017**, last-time-buy 2027-03-31 |
| HB4830-QHTS28 | HTSSOP-28 | Active (pin-compatible successor, see PCN-2026-017 section 4) |
