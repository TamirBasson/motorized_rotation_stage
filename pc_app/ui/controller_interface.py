from __future__ import annotations

from typing import Callable, Protocol

from pc_app.comm import TelemetryPriority, TelemetrySubscription
from pc_app.comm.models import AckMessage, TelemetryState


class StageController(Protocol):
    """UI-facing controller contract.

    The UI depends on this interface instead of touching serial or protocol code directly.
    """

    def rotate_absolute(
        self,
        angle_deg: float,
        virt_zero_offset_deg: float,
        speed_deg_per_sec: float,
        direction: str,
        *,
        timeout: float = 1.0,
    ) -> AckMessage: ...

    def constant_rotate(self, speed_deg_per_sec: float, direction: str, *, timeout: float = 1.0) -> AckMessage: ...

    def rotate_relative(self, delta_angle_deg: float, speed_deg_per_sec: float, *, timeout: float = 1.0) -> AckMessage: ...

    def rotate_mechanical_zero(self, *, timeout: float = 1.0) -> AckMessage: ...

    def rotate_virtual_zero(self, virt_zero_offset_deg: float, *, timeout: float = 1.0) -> AckMessage: ...

    def stop_rotation(self, *, timeout: float = 1.0) -> AckMessage: ...

    def set_telemetry_rate(self, rate_hz: int, *, timeout: float = 1.0) -> AckMessage: ...

    def get_latest_telemetry(self) -> TelemetryState | None: ...

    def subscribe_telemetry(
        self,
        callback: Callable[[TelemetryState], None],
        *,
        replay_latest: bool = True,
        priority: TelemetryPriority = "high",
    ) -> TelemetrySubscription: ...

    def get_virtual_zero_offset_deg(self) -> float | None: ...
