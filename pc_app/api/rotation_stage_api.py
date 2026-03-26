from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from pc_app.comm import (
    AckMessage,
    CommunicationManager,
    TelemetryState,
    TelemetryPriority,
    TelemetrySubscription,
    auto_detect_controller_port,
    build_constant_rotate_command,
    build_rotate_absolute_command,
    build_rotate_home_command,
    build_rotate_relative_command,
    build_rotate_virtual_zero_command,
    build_set_telemetry_rate_command,
    build_stop_command,
)

if TYPE_CHECKING:
    from pc_app.sim.controller_simulator import SimulatorConfig


class RotationStageAPI:
    """High-level Python API that routes all communication through the manager.

    Telemetry from the controller follows: Virtual Degree = Mechanical Degree − Virtual Zero Reference,
    and equivalently Mechanical Degree = Virtual Degree + Virtual Zero Reference (angles normalized to 0–360°).
    """

    def __init__(self, communication_manager: CommunicationManager) -> None:
        self._communication_manager = communication_manager
        self._virtual_zero_offset_deg: float | None = None

    @classmethod
    def from_serial_port(
        cls,
        port: str,
        baudrate: int = 115200,
        *,
        read_timeout: float = 0.1,
        write_timeout: float = 1.0,
    ) -> RotationStageAPI:
        manager = CommunicationManager(
            port=port,
            baudrate=baudrate,
            read_timeout=read_timeout,
            write_timeout=write_timeout,
        )
        return cls(manager)

    @classmethod
    def from_auto_detected_port(
        cls,
        baudrate: int = 115200,
        *,
        read_timeout: float = 0.1,
        write_timeout: float = 1.0,
    ) -> RotationStageAPI:
        return cls.from_serial_port(
            port=auto_detect_controller_port(),
            baudrate=baudrate,
            read_timeout=read_timeout,
            write_timeout=write_timeout,
        )

    @classmethod
    def from_simulator(
        cls,
        *,
        port: str = "SIMULATED_CONTROLLER",
        baudrate: int = 115200,
        read_timeout: float = 0.05,
        write_timeout: float = 1.0,
        simulator_config: SimulatorConfig | None = None,
    ) -> RotationStageAPI:
        from pc_app.sim.controller_simulator import build_simulated_serial_factory

        manager = CommunicationManager(
            port=port,
            baudrate=baudrate,
            read_timeout=read_timeout,
            write_timeout=write_timeout,
            serial_factory=build_simulated_serial_factory(simulator_config),
        )
        return cls(manager)

    @property
    def communication_manager(self) -> CommunicationManager:
        return self._communication_manager

    def start(self) -> None:
        self._communication_manager.start()

    def stop(self) -> None:
        self._communication_manager.stop()

    def rotate_absolute(
        self,
        angle_deg: float,
        virt_zero_offset_deg: float,
        speed_deg_per_sec: float,
        direction: str,
        *,
        timeout: float = 1.0,
    ) -> AckMessage:
        self._virtual_zero_offset_deg = virt_zero_offset_deg
        return self._communication_manager.send_command(
            build_rotate_absolute_command(
                angle_deg=angle_deg,
                virt_zero_offset_deg=virt_zero_offset_deg,
                speed_deg_per_sec=speed_deg_per_sec,
                direction=direction,
            ),
            timeout=timeout,
        )

    def constant_rotate(self, speed_deg_per_sec: float, direction: str, *, timeout: float = 1.0) -> AckMessage:
        return self._communication_manager.send_command(
            build_constant_rotate_command(speed_deg_per_sec=speed_deg_per_sec, direction=direction),
            timeout=timeout,
        )

    def rotate_relative(
        self,
        delta_angle_deg: float,
        speed_deg_per_sec: float,
        direction: str,
        *,
        timeout: float = 1.0,
    ) -> AckMessage:
        return self._communication_manager.send_command(
            build_rotate_relative_command(
                delta_angle_deg=delta_angle_deg,
                speed_deg_per_sec=speed_deg_per_sec,
                direction=direction,
            ),
            timeout=timeout,
        )

    def rotate_mechanical_zero(self, *, timeout: float = 1.0) -> AckMessage:
        return self._communication_manager.send_command(build_rotate_home_command(), timeout=timeout)

    def rotate_virtual_zero(self, virt_zero_offset_deg: float, *, timeout: float = 1.0) -> AckMessage:
        self._virtual_zero_offset_deg = virt_zero_offset_deg
        return self._communication_manager.send_command(
            build_rotate_virtual_zero_command(virt_zero_offset_deg=virt_zero_offset_deg),
            timeout=timeout,
        )

    def stop_rotation(self, *, timeout: float = 1.0) -> AckMessage:
        return self._communication_manager.send_command(build_stop_command(), timeout=timeout)

    def set_telemetry_rate(self, rate_hz: int, *, timeout: float = 1.0) -> AckMessage:
        return self._communication_manager.send_command(
            build_set_telemetry_rate_command(rate_hz=rate_hz),
            timeout=timeout,
        )

    def get_latest_telemetry(self) -> TelemetryState | None:
        return self._communication_manager.get_latest_telemetry()

    def subscribe_telemetry(
        self,
        callback: Callable[[TelemetryState], None],
        *,
        replay_latest: bool = True,
        priority: TelemetryPriority = "high",
    ) -> TelemetrySubscription:
        return self._communication_manager.subscribe_telemetry(
            callback,
            replay_latest=replay_latest,
            priority=priority,
        )

    def get_virtual_zero_offset_deg(self) -> float | None:
        return self._virtual_zero_offset_deg
