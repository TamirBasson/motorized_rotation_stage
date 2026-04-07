from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Protocol

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
    build_stop_command,
)
from pc_app.comm.remote_client import RemoteCommunicationClient
from pc_app.comm.remote_server import DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT

if TYPE_CHECKING:
    from pc_app.sim.controller_simulator import SimulatorConfig


class CommunicationBackend(Protocol):
    def start(self) -> None: ...

    def stop(self) -> None: ...

    def send_command(self, command_line: str, timeout: float = 1.0) -> AckMessage: ...

    def get_latest_telemetry(self) -> TelemetryState | None: ...

    def subscribe_telemetry(
        self,
        callback: Callable[[TelemetryState], None],
        *,
        replay_latest: bool = True,
        priority: TelemetryPriority = "high",
    ) -> TelemetrySubscription: ...

class RotationStageAPI:
    """High-level Python API that routes all communication through the manager.

    Telemetry from the controller follows: Virtual Degree = Mechanical Degree − Virtual Zero Reference,
    and equivalently Mechanical Degree = Virtual Degree + Virtual Zero Reference (angles normalized to 0–360°).
    """

    def __init__(self, communication_backend: CommunicationBackend) -> None:
        self._communication_backend = communication_backend
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

    @classmethod
    def from_server(
        cls,
        *,
        host: str = DEFAULT_SERVER_HOST,
        port: int = DEFAULT_SERVER_PORT,
        client_name: str = "Python API",
        auto_acquire_control: bool = False,
        connect_timeout: float = 2.0,
    ) -> RotationStageAPI:
        return cls(
            RemoteCommunicationClient(
                host=host,
                port=port,
                client_type="api",
                client_name=client_name,
                auto_acquire_control=auto_acquire_control,
                connect_timeout=connect_timeout,
            )
        )

    @property
    def communication_manager(self) -> CommunicationBackend:
        return self._communication_backend

    def start(self) -> None:
        self._communication_backend.start()

    def stop(self) -> None:
        self._communication_backend.stop()

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
        return self._communication_backend.send_command(
            build_rotate_absolute_command(
                angle_deg=angle_deg,
                virt_zero_offset_deg=virt_zero_offset_deg,
                speed_deg_per_sec=speed_deg_per_sec,
                direction=direction,
            ),
            timeout=timeout,
        )

    def constant_rotate(self, speed_deg_per_sec: float, direction: str, *, timeout: float = 1.0) -> AckMessage:
        return self._communication_backend.send_command(
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
        return self._communication_backend.send_command(
            build_rotate_relative_command(
                delta_angle_deg=delta_angle_deg,
                speed_deg_per_sec=speed_deg_per_sec,
                direction=direction,
            ),
            timeout=timeout,
        )

    def rotate_mechanical_zero(self, *, timeout: float = 1.0) -> AckMessage:
        return self._communication_backend.send_command(build_rotate_home_command(), timeout=timeout)

    def rotate_virtual_zero(self, virt_zero_offset_deg: float, *, timeout: float = 1.0) -> AckMessage:
        self._virtual_zero_offset_deg = virt_zero_offset_deg
        return self._communication_backend.send_command(
            build_rotate_virtual_zero_command(virt_zero_offset_deg=virt_zero_offset_deg),
            timeout=timeout,
        )

    def stop_rotation(self, *, timeout: float = 1.0) -> AckMessage:
        return self._communication_backend.send_command(build_stop_command(), timeout=timeout)

    def set_telemetry_rate(self, rate_hz: int, *, timeout: float = 1.0) -> AckMessage:
        set_telemetry_rate = getattr(self._communication_backend, "set_telemetry_rate", None)
        if set_telemetry_rate is not None:
            return set_telemetry_rate(rate_hz, timeout=timeout)
        from pc_app.comm.protocol import build_set_telemetry_rate_command

        return self._communication_backend.send_command(
            build_set_telemetry_rate_command(rate_hz=rate_hz),
            timeout=timeout,
        )

    def get_latest_telemetry(self) -> TelemetryState | None:
        return self._communication_backend.get_latest_telemetry()

    def subscribe_telemetry(
        self,
        callback: Callable[[TelemetryState], None],
        *,
        replay_latest: bool = True,
        priority: TelemetryPriority = "high",
    ) -> TelemetrySubscription:
        return self._communication_backend.subscribe_telemetry(
            callback,
            replay_latest=replay_latest,
            priority=priority,
        )

    def get_virtual_zero_offset_deg(self) -> float | None:
        if self._virtual_zero_offset_deg is not None:
            return self._virtual_zero_offset_deg
        get_virtual_zero_offset_deg = getattr(self._communication_backend, "get_virtual_zero_offset_deg", None)
        if get_virtual_zero_offset_deg is None:
            return None
        return get_virtual_zero_offset_deg()

    def acquire_control(self, *, timeout: float = 1.0) -> bool:
        acquire_control = getattr(self._communication_backend, "acquire_control", None)
        if acquire_control is None:
            return False
        acquire_control(timeout=timeout)
        return True

    def release_control(self, *, timeout: float = 1.0) -> bool:
        release_control = getattr(self._communication_backend, "release_control", None)
        if release_control is None:
            return False
        release_control(timeout=timeout)
        return True
