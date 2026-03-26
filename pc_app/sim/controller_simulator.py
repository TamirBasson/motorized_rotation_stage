from __future__ import annotations

import math
import threading
import time
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from queue import Empty, Queue

from pc_app.comm.models import MotionDirection


@dataclass(slots=True)
class SimulatorConfig:
    motor_steps_per_revolution: float = 200.0
    gear_ratio: float = 180.0
    default_seek_speed_deg_per_sec: float = 5.0
    motion_tick_seconds: float = 0.02
    initial_steps: int = 0
    initial_virtual_zero_offset_deg: float = 0.0
    home_sensor_enabled: bool = True

    @property
    def stage_steps_per_revolution(self) -> int:
        return int(round(self.motor_steps_per_revolution * self.gear_ratio))


class ControllerState(str, Enum):
    IDLE = "IDLE"
    MOVING_ABSOLUTE = "MOVING_ABSOLUTE"
    MOVING_RELATIVE = "MOVING_RELATIVE"
    CONSTANT_ROTATE = "CONSTANT_ROTATE"
    HOMING_MECHANICAL_ZERO = "HOMING_MECHANICAL_ZERO"
    MOVING_TO_VIRTUAL_ZERO = "MOVING_TO_VIRTUAL_ZERO"
    ERROR = "ERROR"


class SimulatedControllerSerial:
    """Serial-compatible controller simulator that speaks the production protocol."""

    def __init__(
        self,
        *,
        port: str,
        baudrate: int,
        timeout: float = 0.1,
        write_timeout: float = 1.0,
        config: SimulatorConfig | None = None,
    ) -> None:
        del baudrate, write_timeout

        self._port = port
        self._timeout = timeout
        self._config = deepcopy(config) if config is not None else SimulatorConfig()
        self._steps_per_revolution = self._config.stage_steps_per_revolution

        self._lock = threading.Lock()
        self._closed = threading.Event()
        self._outbound_lines: Queue[bytes] = Queue()

        self._state = ControllerState.IDLE
        self._direction = MotionDirection.CW
        self._last_telemetry_direction = MotionDirection.CW
        self._commanded_speed_deg_per_sec = 0.0
        self._target_steps = self._config.initial_steps
        self._home_search_start_steps = self._config.initial_steps
        self._telemetry_rate_hz = 0
        self._virtual_zero_offset_deg = self._config.initial_virtual_zero_offset_deg
        self._steps = self._config.initial_steps
        self._step_residual = 0.0
        self._last_telemetry_time = time.monotonic()

        self._thread = threading.Thread(
            target=self._simulation_loop,
            name=f"rotation-stage-simulator-{self._port}",
            daemon=True,
        )
        self._thread.start()

    def readline(self) -> bytes:
        if self._closed.is_set() and self._outbound_lines.empty():
            return b""

        try:
            return self._outbound_lines.get(timeout=self._timeout)
        except Empty:
            return b""

    def write(self, payload: bytes) -> int:
        if self._closed.is_set():
            raise OSError(f"Simulated controller on {self._port} is closed")

        command_text = payload.decode("ascii")
        for line in command_text.splitlines():
            normalized = line.strip()
            if normalized:
                self._process_command_line(normalized)
        return len(payload)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self._closed.set()
        self._thread.join(timeout=1.0)

    def _simulation_loop(self) -> None:
        last_update = time.monotonic()
        while not self._closed.wait(self._config.motion_tick_seconds):
            now = time.monotonic()
            delta_seconds = max(0.0, now - last_update)
            last_update = now

            outbound_lines: list[str] = []
            with self._lock:
                motion_event = self._advance_motion_locked(delta_seconds)
                if motion_event is not None:
                    outbound_lines.append(motion_event)

                if self._telemetry_rate_hz > 0:
                    interval = 1.0 / self._telemetry_rate_hz
                    if (now - self._last_telemetry_time) >= interval:
                        self._last_telemetry_time = now
                        outbound_lines.append(self._build_telemetry_line_locked())

            for outbound_line in outbound_lines:
                self._enqueue_line(outbound_line)

    def _process_command_line(self, line: str) -> None:
        fields = line.split(",")
        outbound_lines: list[str]
        with self._lock:
            outbound_lines = self._handle_command_locked(fields)

        for outbound_line in outbound_lines:
            self._enqueue_line(outbound_line)

    def _handle_command_locked(self, fields: list[str]) -> list[str]:
        if len(fields) < 2:
            return [self._build_err("BAD_FORMAT", "MESSAGE")]

        if fields[0] != "CMD":
            return [self._build_err("UNKNOWN_COMMAND", fields[0])]

        command = fields[1]
        if command == "ROT_ABS":
            return self._handle_rotate_absolute_locked(fields)
        if command == "ROT_CONST":
            return self._handle_rotate_constant_locked(fields)
        if command == "ROT_REL":
            return self._handle_rotate_relative_locked(fields)
        if command == "ROT_HOME":
            return self._handle_rotate_home_locked(fields)
        if command == "ROT_VZERO":
            return self._handle_rotate_virtual_zero_locked(fields)
        if command == "STOP":
            return self._handle_stop_locked(fields)
        if command == "TLM":
            return self._handle_telemetry_locked(fields)
        return [self._build_err("UNKNOWN_COMMAND", command)]

    def _handle_rotate_absolute_locked(self, fields: list[str]) -> list[str]:
        if len(fields) != 6:
            return [self._build_err("BAD_FIELD_COUNT", "ROT_ABS")]

        angle_deg = self._parse_float(fields[2])
        offset_deg = self._parse_float(fields[3])
        speed_deg_per_sec = self._parse_float(fields[4])
        direction = self._parse_direction(fields[5])
        if angle_deg is None or offset_deg is None or speed_deg_per_sec is None or direction is None:
            return [self._build_err("BAD_FORMAT", "ROT_ABS")]

        if not (
            self._value_in_range(angle_deg, 0.0, 360.0)
            and self._value_in_range(offset_deg, -180.0, 180.0)
            and self._value_in_range(speed_deg_per_sec, 0.1, 20.0)
        ):
            return [self._build_err("PARAM_OUT_OF_RANGE", "ROT_ABS")]

        self._start_absolute_move_locked(angle_deg, offset_deg, speed_deg_per_sec, direction)
        return [f"ACK,ROT_ABS,{angle_deg:.2f},{offset_deg:.2f},{speed_deg_per_sec:.1f},{direction.value}"]

    def _handle_rotate_constant_locked(self, fields: list[str]) -> list[str]:
        if len(fields) != 4:
            return [self._build_err("BAD_FIELD_COUNT", "ROT_CONST")]

        speed_deg_per_sec = self._parse_float(fields[2])
        direction = self._parse_direction(fields[3])
        if speed_deg_per_sec is None or direction is None:
            return [self._build_err("BAD_FORMAT", "ROT_CONST")]

        if not self._value_in_range(speed_deg_per_sec, 0.1, 20.0):
            return [self._build_err("PARAM_OUT_OF_RANGE", "ROT_CONST")]

        self._start_constant_rotate_locked(speed_deg_per_sec, direction)
        return [f"ACK,ROT_CONST,{speed_deg_per_sec:.1f},{direction.value}"]

    def _handle_rotate_relative_locked(self, fields: list[str]) -> list[str]:
        if len(fields) != 4:
            return [self._build_err("BAD_FIELD_COUNT", "ROT_REL")]

        delta_angle_deg = self._parse_float(fields[2])
        speed_deg_per_sec = self._parse_float(fields[3])
        if delta_angle_deg is None or speed_deg_per_sec is None:
            return [self._build_err("BAD_FORMAT", "ROT_REL")]

        if not (
            self._value_in_range(delta_angle_deg, -360.0, 360.0)
            and self._value_in_range(speed_deg_per_sec, 0.1, 20.0)
        ):
            return [self._build_err("PARAM_OUT_OF_RANGE", "ROT_REL")]

        self._start_move_by_delta_locked(delta_angle_deg, speed_deg_per_sec, ControllerState.MOVING_RELATIVE)
        return [f"ACK,ROT_REL,{delta_angle_deg:.2f},{speed_deg_per_sec:.1f}"]

    def _handle_rotate_home_locked(self, fields: list[str]) -> list[str]:
        if len(fields) != 2:
            return [self._build_err("BAD_FIELD_COUNT", "ROT_HOME")]

        self._start_mechanical_homing_locked(self._config.default_seek_speed_deg_per_sec)
        return ["ACK,ROT_HOME"]

    def _handle_rotate_virtual_zero_locked(self, fields: list[str]) -> list[str]:
        if len(fields) != 3:
            return [self._build_err("BAD_FIELD_COUNT", "ROT_VZERO")]

        offset_deg = self._parse_float(fields[2])
        if offset_deg is None:
            return [self._build_err("BAD_FORMAT", "ROT_VZERO")]

        if not self._value_in_range(offset_deg, -180.0, 180.0):
            return [self._build_err("PARAM_OUT_OF_RANGE", "ROT_VZERO")]

        self._start_rotate_to_virtual_zero_locked(offset_deg)
        return [f"ACK,ROT_VZERO,{offset_deg:.2f}"]

    def _handle_stop_locked(self, fields: list[str]) -> list[str]:
        if len(fields) != 2:
            return [self._build_err("BAD_FIELD_COUNT", "STOP")]

        self._stop_now_locked()
        return ["ACK,STOP"]

    def _handle_telemetry_locked(self, fields: list[str]) -> list[str]:
        if len(fields) != 3:
            return [self._build_err("BAD_FIELD_COUNT", "TLM")]

        rate = self._parse_int(fields[2])
        if rate is None:
            return [self._build_err("BAD_FORMAT", "TLM")]

        if rate not in {-1, 0} and not 1 <= rate <= 100:
            return [self._build_err("PARAM_OUT_OF_RANGE", "TLM")]

        if rate == -1:
            return ["ACK,TLM,-1", self._build_telemetry_line_locked()]

        self._telemetry_rate_hz = rate
        self._last_telemetry_time = time.monotonic()
        return [f"ACK,TLM,{rate}"]

    def _start_absolute_move_locked(
        self,
        target_virtual_angle_deg: float,
        offset_deg: float,
        speed_deg_per_sec: float,
        preferred_direction: MotionDirection,
    ) -> None:
        self._virtual_zero_offset_deg = offset_deg
        self._preempt_current_motion_locked()

        current_mechanical_deg = self._get_mechanical_angle_deg_locked()
        target_mechanical_deg = self._normalize_angle_360(target_virtual_angle_deg + self._virtual_zero_offset_deg)
        if preferred_direction == MotionDirection.CW:
            delta_deg = self._clockwise_delta_deg(current_mechanical_deg, target_mechanical_deg)
        else:
            delta_deg = self._counter_clockwise_delta_deg(current_mechanical_deg, target_mechanical_deg)

        self._start_move_by_delta_locked(delta_deg, speed_deg_per_sec, ControllerState.MOVING_ABSOLUTE)

    def _start_move_by_delta_locked(
        self,
        delta_angle_deg: float,
        speed_deg_per_sec: float,
        move_state: ControllerState,
    ) -> None:
        self._preempt_current_motion_locked()

        delta_steps = self._degrees_to_steps(delta_angle_deg)
        if delta_steps == 0:
            self._clear_motion_state_locked(ControllerState.IDLE)
            return

        self._state = move_state
        self._direction = MotionDirection.CW if delta_steps > 0 else MotionDirection.CCW
        self._commanded_speed_deg_per_sec = speed_deg_per_sec
        self._target_steps = self._steps + delta_steps
        self._home_search_start_steps = self._steps
        self._step_residual = 0.0

    def _start_rotate_to_virtual_zero_locked(self, offset_deg: float) -> None:
        self._virtual_zero_offset_deg = offset_deg
        self._preempt_current_motion_locked()

        current_mechanical_deg = self._get_mechanical_angle_deg_locked()
        target_mechanical_deg = self._normalize_angle_360(self._virtual_zero_offset_deg)
        delta_deg = self._shortest_signed_delta_deg(current_mechanical_deg, target_mechanical_deg)
        self._start_move_by_delta_locked(
            delta_deg,
            self._config.default_seek_speed_deg_per_sec,
            ControllerState.MOVING_TO_VIRTUAL_ZERO,
        )

    def _start_constant_rotate_locked(self, speed_deg_per_sec: float, direction: MotionDirection) -> None:
        self._preempt_current_motion_locked()
        self._state = ControllerState.CONSTANT_ROTATE
        self._direction = direction
        self._commanded_speed_deg_per_sec = speed_deg_per_sec
        self._target_steps = self._steps
        self._home_search_start_steps = self._steps
        self._step_residual = 0.0

    def _start_mechanical_homing_locked(self, speed_deg_per_sec: float) -> None:
        self._preempt_current_motion_locked()
        if self._home_sensor_active_now_locked():
            self._steps = 0
            self._clear_motion_state_locked(ControllerState.IDLE)
            return

        self._state = ControllerState.HOMING_MECHANICAL_ZERO
        self._direction = MotionDirection.CCW
        self._commanded_speed_deg_per_sec = speed_deg_per_sec
        self._home_search_start_steps = self._steps
        self._target_steps = self._steps - self._steps_per_revolution
        self._step_residual = 0.0

    def _stop_now_locked(self) -> None:
        self._preempt_current_motion_locked()

    def _preempt_current_motion_locked(self) -> None:
        self._clear_motion_state_locked(ControllerState.IDLE)

    def _clear_motion_state_locked(self, next_state: ControllerState = ControllerState.IDLE) -> None:
        if next_state == ControllerState.IDLE and self._is_motion_state(self._state):
            self._last_telemetry_direction = self._direction

        self._state = next_state
        self._direction = MotionDirection.CW
        self._commanded_speed_deg_per_sec = 0.0
        self._target_steps = self._steps
        self._home_search_start_steps = self._steps
        self._step_residual = 0.0

    def _advance_motion_locked(self, delta_seconds: float) -> str | None:
        if delta_seconds <= 0.0:
            return None

        if self._state == ControllerState.HOMING_MECHANICAL_ZERO:
            moved_steps = self._compute_step_increment_locked(delta_seconds)
            if moved_steps <= 0:
                return None

            previous_steps = self._steps
            self._steps -= moved_steps

            if self._config.home_sensor_enabled and self._crossed_home_sensor(previous_steps, self._steps):
                self._steps = 0
                self._clear_motion_state_locked(ControllerState.IDLE)
                return None

            if abs(self._steps - self._home_search_start_steps) >= self._steps_per_revolution:
                self._clear_motion_state_locked(ControllerState.ERROR)
                return self._build_err("ZERO_NOT_FOUND", "ROT_HOME")
            return None

        if self._state in {
            ControllerState.MOVING_ABSOLUTE,
            ControllerState.MOVING_RELATIVE,
            ControllerState.MOVING_TO_VIRTUAL_ZERO,
        }:
            moved_steps = self._compute_step_increment_locked(delta_seconds)
            if moved_steps <= 0:
                return None

            if self._direction == MotionDirection.CW:
                self._steps = min(self._steps + moved_steps, self._target_steps)
            else:
                self._steps = max(self._steps - moved_steps, self._target_steps)

            if self._steps == self._target_steps:
                self._clear_motion_state_locked(ControllerState.IDLE)
            return None

        if self._state == ControllerState.CONSTANT_ROTATE:
            moved_steps = self._compute_step_increment_locked(delta_seconds)
            if moved_steps <= 0:
                return None

            if self._direction == MotionDirection.CW:
                self._steps += moved_steps
            else:
                self._steps -= moved_steps

        return None

    def _compute_step_increment_locked(self, delta_seconds: float) -> int:
        speed_steps_per_second = self._degrees_per_second_to_step_hz(self._commanded_speed_deg_per_sec)
        desired_steps = (speed_steps_per_second * delta_seconds) + self._step_residual
        whole_steps = int(desired_steps)
        self._step_residual = desired_steps - whole_steps
        return whole_steps

    def _build_telemetry_line_locked(self) -> str:
        is_running = self._state not in {ControllerState.IDLE, ControllerState.ERROR}
        reported_speed = self._commanded_speed_deg_per_sec if is_running else 0.0
        reported_direction = self._direction if is_running else self._last_telemetry_direction
        return (
            f"TLM,{self._get_mechanical_angle_deg_locked():.2f},{self._get_virtual_angle_deg_locked():.2f},"
            f"{1 if is_running else 0},{reported_speed:.2f},{reported_direction.value},{self._steps}"
        )

    def _get_mechanical_angle_deg_locked(self) -> float:
        return self._normalize_angle_360(self._steps_to_degrees(self._steps))

    def _get_virtual_angle_deg_locked(self) -> float:
        return self._normalize_angle_360(self._get_mechanical_angle_deg_locked() - self._virtual_zero_offset_deg)

    def _home_sensor_active_now_locked(self) -> bool:
        if not self._config.home_sensor_enabled:
            return False
        return self._steps % self._steps_per_revolution == 0

    def _crossed_home_sensor(self, previous_steps: int, current_steps: int) -> bool:
        if previous_steps == current_steps:
            return self._home_sensor_active_now_locked()

        lower_bound = min(previous_steps, current_steps)
        upper_bound = max(previous_steps, current_steps)
        first_multiple = math.ceil(lower_bound / self._steps_per_revolution) * self._steps_per_revolution
        return first_multiple <= upper_bound

    def _degrees_to_steps(self, angle_deg: float) -> int:
        return self._round_to_int32((angle_deg * self._steps_per_revolution) / 360.0)

    def _steps_to_degrees(self, steps: int) -> float:
        return (steps * 360.0) / self._steps_per_revolution

    def _degrees_per_second_to_step_hz(self, speed_deg_per_sec: float) -> float:
        return (speed_deg_per_sec * self._steps_per_revolution) / 360.0

    @staticmethod
    def _build_err(code: str, details: str) -> str:
        return f"ERR,{code},{details}"

    @staticmethod
    def _normalize_angle_360(angle_deg: float) -> float:
        wrapped = math.fmod(angle_deg, 360.0)
        if wrapped < 0.0:
            wrapped += 360.0
        if wrapped >= 360.0:
            wrapped -= 360.0
        return wrapped

    @staticmethod
    def _shortest_signed_delta_deg(current_deg: float, target_deg: float) -> float:
        delta = SimulatedControllerSerial._normalize_angle_360(target_deg - current_deg)
        if delta > 180.0:
            delta -= 360.0
        return delta

    @staticmethod
    def _clockwise_delta_deg(current_deg: float, target_deg: float) -> float:
        return SimulatedControllerSerial._normalize_angle_360(target_deg - current_deg)

    @staticmethod
    def _counter_clockwise_delta_deg(current_deg: float, target_deg: float) -> float:
        return -SimulatedControllerSerial._normalize_angle_360(current_deg - target_deg)

    @staticmethod
    def _round_to_int32(value: float) -> int:
        return int(value + 0.5) if value >= 0.0 else int(value - 0.5)

    @staticmethod
    def _value_in_range(value: float, minimum: float, maximum: float) -> bool:
        return minimum <= value <= maximum

    @staticmethod
    def _parse_float(raw_value: str) -> float | None:
        try:
            value = float(raw_value)
        except ValueError:
            return None
        return value if math.isfinite(value) else None

    @staticmethod
    def _parse_int(raw_value: str) -> int | None:
        try:
            return int(raw_value)
        except ValueError:
            return None

    @staticmethod
    def _parse_direction(raw_value: str) -> MotionDirection | None:
        if raw_value == MotionDirection.CW.value:
            return MotionDirection.CW
        if raw_value == MotionDirection.CCW.value:
            return MotionDirection.CCW
        return None

    @staticmethod
    def _is_motion_state(state: ControllerState) -> bool:
        return state in {
            ControllerState.MOVING_ABSOLUTE,
            ControllerState.MOVING_RELATIVE,
            ControllerState.CONSTANT_ROTATE,
            ControllerState.HOMING_MECHANICAL_ZERO,
            ControllerState.MOVING_TO_VIRTUAL_ZERO,
        }

    def _enqueue_line(self, line: str) -> None:
        self._outbound_lines.put(f"{line}\r\n".encode("ascii"))


def build_simulated_serial_factory(config: SimulatorConfig | None = None):
    config_snapshot = deepcopy(config) if config is not None else SimulatorConfig()

    def factory(*, port: str, baudrate: int, timeout: float, write_timeout: float) -> SimulatedControllerSerial:
        return SimulatedControllerSerial(
            port=port,
            baudrate=baudrate,
            timeout=timeout,
            write_timeout=write_timeout,
            config=deepcopy(config_snapshot),
        )

    return factory
