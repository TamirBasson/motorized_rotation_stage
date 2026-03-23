from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias


class MotionDirection(str, Enum):
    CW = "CW"
    CCW = "CCW"


@dataclass(frozen=True, slots=True)
class AckMessage:
    command_type: str
    parameters: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ErrMessage:
    error_code: str
    details: str


@dataclass(frozen=True, slots=True)
class TelemetryState:
    mechanical_angle_deg: float
    virtual_angle_deg: float
    running: bool
    speed_deg_per_sec: float
    direction: MotionDirection
    steps: int


ParsedInboundMessage: TypeAlias = AckMessage | ErrMessage | TelemetryState
