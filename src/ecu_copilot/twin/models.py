"""Pydantic models = the contract of the twin API (and the schema in /docs)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class Variant(StrEnum):
    A = "A"  # DCU-A1: basic door control unit
    B = "B"  # DCU-B2: with keyless entry antenna pre-processing (higher quiescent current)


class Verdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"


class Measurements(BaseModel):
    quiescent_current_ua: float = Field(description="Sleep current in µA at 12 V")
    operating_current_a: float = Field(description="Window lift run current in A")
    flash_time_s: float = Field(description="Firmware flash + verify duration in s")
    board_temp_c: float = Field(description="PCB temperature at test in °C")
    ambient_noise_db: float = Field(description="Background noise at the acoustic cell in dB(A)")
    acoustic_score: float = Field(description="Acoustic classifier score 0-100 (higher = quieter)")
    lin_comm_ok: bool = Field(description="LIN bus communication check passed")


class TestResult(BaseModel):
    id: int
    timestamp: datetime
    station: int
    variant: Variant
    serial: str
    lot: str
    measurements: Measurements
    verdict: Verdict
    failure_code: str | None = Field(default=None, description="E-xxx code from the EOL spec, if failed")


class StationInfo(BaseModel):
    station: int
    name: str
    variants: list[Variant]
    interval_s: float


# --- Faults (what an operator or the demo can inject) --------------------------
class TemperatureDrift(BaseModel):
    type: Literal["temperature_drift"] = "temperature_drift"
    station: int
    delta_c: float = Field(default=10.0, description="Temperature rise at steady state in K")
    ramp_s: float = Field(default=60.0, description="Seconds until the full rise is reached")


class AcousticNoise(BaseModel):
    type: Literal["acoustic_noise"] = "acoustic_noise"
    station: int
    noise_db: float = Field(default=57.0, description="Background noise level in dB(A)")


class BadLot(BaseModel):
    type: Literal["bad_lot"] = "bad_lot"
    variant: Variant = Variant.B
    lot: str = "L2439-07"
    fail_rate: float = Field(default=0.15, ge=0, le=1, description="Share of units with a LIN fault")


class SensorOffset(BaseModel):
    """The station's T1 sensor reads wrong: the REPORTED temperature is offset, the physical one is not.
    Quiescent current therefore does not follow the reported T1 - the decoupling signature."""

    type: Literal["sensor_offset"] = "sensor_offset"
    station: int
    offset_c: float = Field(default=9.0, description="Reported minus physical temperature in K")


Fault = TemperatureDrift | AcousticNoise | BadLot | SensorOffset


class ActiveFault(BaseModel):
    id: int
    started_at: datetime
    fault: Fault


# --- Statistics ----------------------------------------------------------------
class GroupStats(BaseModel):
    station: int
    variant: Variant
    tested: int
    failed: int
    failure_rate_pct: float
    failure_codes: dict[str, int]
    mean_board_temp_c: float | None
    mean_ambient_noise_db: float | None
    mean_quiescent_current_ua: float | None
    mean_acoustic_score: float | None


class StatsResponse(BaseModel):
    window_minutes: int
    from_time: datetime
    to_time: datetime
    groups: list[GroupStats]
