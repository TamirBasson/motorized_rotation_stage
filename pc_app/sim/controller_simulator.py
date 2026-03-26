from __future__ import annotations

"""Firmware-style controller simulator used by the PC application.

This file creates an in-process fake controller that looks like a serial device to
the CommunicationManager. The UI and API send normal protocol commands, and this
simulator responds with normal ACK / ERR / TLM lines, so end-to-end behavior can
be tested without a real Arduino or motor.

Internally it keeps firmware-like runtime state, advances motion over time on a
background thread, converts between angles and steps, and applies the same ideas
as the planned firmware: non-blocking command handling, periodic telemetry, and
immediate override of the currently active motion.
"""

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
    # Match the firmware defaults so PC-side tests see realistic step/angle behavior.
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
    # These states intentionally mirror the firmware state machine described in the docs.
    IDLE = "IDLE"
    MOVING_ABSOLUTE = "MOVING_ABSOLUTE"
    MOVING_RELATIVE = "MOVING_RELATIVE"
    CONSTANT_ROTATE = "CONSTANT_ROTATE"
    HOMING_MECHANICAL_ZERO = "HOMING_MECHANICAL_ZERO"
    MOVING_TO_VIRTUAL_ZERO = "MOVING_TO_VIRTUAL_ZERO"
    ERROR = "ERROR"


class SimulatedControllerSerial:
    """Serial-compatible controller simulator that speaks the production protocol.

    From the CommunicationManager's point of view, this object behaves like a serial
    port. From the simulator's point of view, it is the whole fake controller:
    command parser, motion state machine, telemetry source, and protocol responder.
    """

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
        # This is the core conversion constant used everywhere for angle <-> step math.
        self._steps_per_revolution = self._config.stage_steps_per_revolution

        self._lock = threading.Lock()
        self._closed = threading.Event()
        # The CommunicationManager reads from this queue as if it were a serial RX buffer.
        self._outbound_lines: Queue[bytes] = Queue()

        # These fields mirror the firmware runtime snapshot: motion state, current step position,
        # target position, telemetry settings, and virtual-zero configuration.
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

    # Serial API expected by CommunicationManager: block briefly, then return one line.
    def readline(self) -> bytes:
        if self._closed.is_set() and self._outbound_lines.empty():
            return b""

        try:
            return self._outbound_lines.get(timeout=self._timeout)
        except Empty:
            return b""

    # Serial API expected by CommunicationManager: accept outbound controller commands.
    def write(self, payload: bytes) -> int:
        if self._closed.is_set():
            raise OSError(f"Simulated controller on {self._port} is closed")

        # A real controller receives newline-terminated ASCII commands over serial.
        command_text = payload.decode("ascii")
        for line in command_text.splitlines():
            normalized = line.strip()
            if normalized:
                self._process_command_line(normalized)
        return len(payload)

    def flush(self) -> None:
        return None

    # Stop the background firmware loop and behave like a closed serial device.
    def close(self) -> None:
        self._closed.set()
        self._thread.join(timeout=1.0)

    # Main background loop that imitates the firmware's "update motion, then service telemetry" flow.
    def _simulation_loop(self) -> None:
        last_update = time.monotonic()
        while not self._closed.wait(self._config.motion_tick_seconds):
            now = time.monotonic()
            delta_seconds = max(0.0, now - last_update)
            last_update = now

            outbound_lines: list[str] = []
            with self._lock:
                # Advance the motor model a small amount each tick so motion is gradual.
                motion_event = self._advance_motion_locked(delta_seconds)
                if motion_event is not None:
                    outbound_lines.append(motion_event)

                # Telemetry is scheduled independently of command handling, like the firmware loop.
                if self._telemetry_rate_hz > 0:
                    interval = 1.0 / self._telemetry_rate_hz
                    if (now - self._last_telemetry_time) >= interval:
                        self._last_telemetry_time = now
                        outbound_lines.append(self._build_telemetry_line_locked())

            for outbound_line in outbound_lines:
                self._enqueue_line(outbound_line)

    # Parse one full protocol line exactly as the embedded controller would receive it.
    def _process_command_line(self, line: str) -> None:
        fields = line.split(",")
        outbound_lines: list[str]
        with self._lock:
            outbound_lines = self._handle_command_locked(fields)

        for outbound_line in outbound_lines:
            self._enqueue_line(outbound_line)

    # Top-level command dispatcher: validate the family, then route to the specific handler.
    def _handle_command_locked(self, fields: list[str]) -> list[str]:
        if len(fields) < 2:
            return [self._build_err("BAD_FORMAT", "MESSAGE")]

        if fields[0] != "CMD":
            return [self._build_err("UNKNOWN_COMMAND", fields[0])]

        # Keep dispatch simple and explicit so it stays close to the single-file firmware parser.
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

    # Handle ROT_ABS: validate parameters, convert virtual-angle intent into mechanical motion,
    # and return the same ACK shape that the real firmware would emit.
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

    # Handle ROT_CONST: start indefinite motion that continues until another command overrides it.
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

    # Handle ROT_REL: move by a positive delta in the explicit commanded direction.
    def _handle_rotate_relative_locked(self, fields: list[str]) -> list[str]:
        if len(fields) != 5:
            return [self._build_err("BAD_FIELD_COUNT", "ROT_REL")]

        delta_angle_deg = self._parse_float(fields[2])
        speed_deg_per_sec = self._parse_float(fields[3])
        direction = self._parse_direction(fields[4])
        if delta_angle_deg is None or speed_deg_per_sec is None or direction is None:
            return [self._build_err("BAD_FORMAT", "ROT_REL")]

        if not (
            self._value_in_range(delta_angle_deg, 0.0, 360.0)
            and self._value_in_range(speed_deg_per_sec, 0.1, 20.0)
        ):
            return [self._build_err("PARAM_OUT_OF_RANGE", "ROT_REL")]

        signed_delta_deg = delta_angle_deg if direction == MotionDirection.CW else -delta_angle_deg
        self._start_move_by_delta_locked(signed_delta_deg, speed_deg_per_sec, ControllerState.MOVING_RELATIVE)
        return [f"ACK,ROT_REL,{delta_angle_deg:.2f},{speed_deg_per_sec:.1f},{direction.value}"]

    # Handle ROT_HOME: begin a homing search that moves until the simulated home sensor is crossed.
    def _handle_rotate_home_locked(self, fields: list[str]) -> list[str]:
        if len(fields) != 2:
            return [self._build_err("BAD_FIELD_COUNT", "ROT_HOME")]

        self._start_mechanical_homing_locked(self._config.default_seek_speed_deg_per_sec)
        return ["ACK,ROT_HOME"]

    # Handle ROT_VZERO: change the virtual offset and move so the reported virtual angle becomes zero.
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

    # Handle STOP: immediately preempt the current motion state.
    def _handle_stop_locked(self, fields: list[str]) -> list[str]:
        if len(fields) != 2:
            return [self._build_err("BAD_FIELD_COUNT", "STOP")]

        self._stop_now_locked()
        return ["ACK,STOP"]

    # Handle TLM: either change cyclic telemetry rate or emit one sample immediately.
    def _handle_telemetry_locked(self, fields: list[str]) -> list[str]:
        if len(fields) != 3:
            return [self._build_err("BAD_FIELD_COUNT", "TLM")]

        rate = self._parse_int(fields[2])
        if rate is None:
            return [self._build_err("BAD_FORMAT", "TLM")]

        if rate not in {-1, 0} and not 1 <= rate <= 100:
            return [self._build_err("PARAM_OUT_OF_RANGE", "TLM")]

        if rate == -1:
            # The protocol defines -1 as "ACK now, then send one telemetry sample immediately".
            return ["ACK,TLM,-1", self._build_telemetry_line_locked()]

        self._telemetry_rate_hz = rate
        self._last_telemetry_time = time.monotonic()
        return [f"ACK,TLM,{rate}"]

    # Convert an absolute command in virtual coordinates into the mechanical delta that the motor must run.
    def _start_absolute_move_locked(
        self,
        target_virtual_angle_deg: float,
        offset_deg: float,
        speed_deg_per_sec: float,
        preferred_direction: MotionDirection,
    ) -> None:
        # The command is expressed in virtual-angle space, but motion runs in mechanical space.
        self._virtual_zero_offset_deg = offset_deg
        self._preempt_current_motion_locked()

        current_mechanical_deg = self._get_mechanical_angle_deg_locked()
        target_mechanical_deg = self._normalize_angle_360(target_virtual_angle_deg + self._virtual_zero_offset_deg)
        if preferred_direction == MotionDirection.CW:
            delta_deg = self._clockwise_delta_deg(current_mechanical_deg, target_mechanical_deg)
        else:
            delta_deg = self._counter_clockwise_delta_deg(current_mechanical_deg, target_mechanical_deg)

        self._start_move_by_delta_locked(delta_deg, speed_deg_per_sec, ControllerState.MOVING_ABSOLUTE)

    # Common entry point for finite moves: convert degrees to steps and populate the motion state.
    def _start_move_by_delta_locked(
        self,
        delta_angle_deg: float,
        speed_deg_per_sec: float,
        move_state: ControllerState,
    ) -> None:
        self._preempt_current_motion_locked()

        delta_steps = self._degrees_to_steps(delta_angle_deg)
        if delta_steps == 0:
            # Zero-distance commands are valid; they just do not enter a moving state.
            self._clear_motion_state_locked(ControllerState.IDLE)
            return

        self._state = move_state
        self._direction = MotionDirection.CW if delta_steps > 0 else MotionDirection.CCW
        self._commanded_speed_deg_per_sec = speed_deg_per_sec
        self._target_steps = self._steps + delta_steps
        self._home_search_start_steps = self._steps
        self._step_residual = 0.0

    # Move to the position where the reported virtual angle becomes zero.
    def _start_rotate_to_virtual_zero_locked(self, offset_deg: float) -> None:
        self._virtual_zero_offset_deg = offset_deg
        self._preempt_current_motion_locked()

        current_mechanical_deg = self._get_mechanical_angle_deg_locked()
        # Firmware behavior: move until virtual angle becomes zero, which means
        # mechanical_angle == virtual_zero_offset.
        target_mechanical_deg = self._normalize_angle_360(self._virtual_zero_offset_deg)
        delta_deg = self._shortest_signed_delta_deg(current_mechanical_deg, target_mechanical_deg)
        self._start_move_by_delta_locked(
            delta_deg,
            self._config.default_seek_speed_deg_per_sec,
            ControllerState.MOVING_TO_VIRTUAL_ZERO,
        )

    # Start an "infinite" rotation state. No fixed target is used; the step count just keeps changing.
    def _start_constant_rotate_locked(self, speed_deg_per_sec: float, direction: MotionDirection) -> None:
        self._preempt_current_motion_locked()
        self._state = ControllerState.CONSTANT_ROTATE
        self._direction = direction
        self._commanded_speed_deg_per_sec = speed_deg_per_sec
        self._target_steps = self._steps
        self._home_search_start_steps = self._steps
        self._step_residual = 0.0

    # Start homing by rotating CCW until the simulated home switch is hit or one revolution is exceeded.
    def _start_mechanical_homing_locked(self, speed_deg_per_sec: float) -> None:
        self._preempt_current_motion_locked()
        if self._home_sensor_active_now_locked():
            # If the stage already sits on the home sensor, homing completes immediately.
            self._steps = 0
            self._clear_motion_state_locked(ControllerState.IDLE)
            return

        self._state = ControllerState.HOMING_MECHANICAL_ZERO
        self._direction = MotionDirection.CCW
        self._commanded_speed_deg_per_sec = speed_deg_per_sec
        self._home_search_start_steps = self._steps
        self._target_steps = self._steps - self._steps_per_revolution
        self._step_residual = 0.0

    # Stop is modeled as the same immediate preemption that any newer command would cause.
    def _stop_now_locked(self) -> None:
        self._preempt_current_motion_locked()

    # Firmware rule: a newly accepted command overrides the current motion without waiting for completion.
    def _preempt_current_motion_locked(self) -> None:
        # New commands override old ones immediately, matching the architecture docs.
        self._clear_motion_state_locked(ControllerState.IDLE)

    # Reset the active-motion fields while preserving the direction needed for idle telemetry reporting.
    def _clear_motion_state_locked(self, next_state: ControllerState = ControllerState.IDLE) -> None:
        if next_state == ControllerState.IDLE and self._is_motion_state(self._state):
            # Idle telemetry should still report the most recently commanded direction.
            self._last_telemetry_direction = self._direction

        self._state = next_state
        self._direction = MotionDirection.CW
        self._commanded_speed_deg_per_sec = 0.0
        self._target_steps = self._steps
        self._home_search_start_steps = self._steps
        self._step_residual = 0.0

    # Advance the firmware state machine by one time slice and update internal steps accordingly.
    # This is the key method that makes motion gradual instead of jumping straight to the destination.
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
                # Crossing the virtual home switch rebases the internal position to exactly zero.
                self._steps = 0
                self._clear_motion_state_locked(ControllerState.IDLE)
                return None

            if abs(self._steps - self._home_search_start_steps) >= self._steps_per_revolution:
                self._clear_motion_state_locked(ControllerState.ERROR)
                return self._build_err("ZERO_NOT_FOUND", "ROT_HOME")
            return None

        # These states all share the same "move toward a finite target step" behavior.
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

            # Clamp to the target so the simulator finishes cleanly without oscillating around it.
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

    # Convert elapsed time and commanded speed into a whole-step increment for this tick.
    def _compute_step_increment_locked(self, delta_seconds: float) -> int:
        speed_steps_per_second = self._degrees_per_second_to_step_hz(self._commanded_speed_deg_per_sec)
        desired_steps = (speed_steps_per_second * delta_seconds) + self._step_residual
        whole_steps = int(desired_steps)
        # Preserve the fractional remainder so small tick intervals still integrate to the right speed.
        self._step_residual = desired_steps - whole_steps
        return whole_steps

    # Build the exact ASCII telemetry line consumed by the existing protocol parser on the PC side.
    def _build_telemetry_line_locked(self) -> str:
        is_running = self._state not in {ControllerState.IDLE, ControllerState.ERROR}
        reported_speed = self._commanded_speed_deg_per_sec if is_running else 0.0
        reported_direction = self._direction if is_running else self._last_telemetry_direction
        return (
            f"TLM,{self._get_mechanical_angle_deg_locked():.2f},{self._get_virtual_angle_deg_locked():.2f},"
            f"{1 if is_running else 0},{reported_speed:.2f},{reported_direction.value},{self._steps}"
        )

    # Mechanical angle is the physical position derived from the internal step count.
    def _get_mechanical_angle_deg_locked(self) -> float:
        return self._normalize_angle_360(self._steps_to_degrees(self._steps))

    # Virtual angle is the operator-facing angle after applying the configured software offset.
    def _get_virtual_angle_deg_locked(self) -> float:
        # Virtual angle is a view of the same physical position in a shifted reference frame.
        return self._normalize_angle_360(self._get_mechanical_angle_deg_locked() - self._virtual_zero_offset_deg)

    # The simulated home sensor is active at each full revolution boundary when enabled.
    def _home_sensor_active_now_locked(self) -> bool:
        if not self._config.home_sensor_enabled:
            return False
        return self._steps % self._steps_per_revolution == 0

    # Detect whether the motion during this tick crossed the home-switch position.
    def _crossed_home_sensor(self, previous_steps: int, current_steps: int) -> bool:
        if previous_steps == current_steps:
            return self._home_sensor_active_now_locked()

        # Detect whether the step interval crossed any full-revolution boundary.
        lower_bound = min(previous_steps, current_steps)
        upper_bound = max(previous_steps, current_steps)
        first_multiple = math.ceil(lower_bound / self._steps_per_revolution) * self._steps_per_revolution
        return first_multiple <= upper_bound

    # These conversion helpers are the bridge between user-facing angle commands and motor-facing step math.
    def _degrees_to_steps(self, angle_deg: float) -> int:
        return self._round_to_int32((angle_deg * self._steps_per_revolution) / 360.0)

    def _steps_to_degrees(self, steps: int) -> float:
        return (steps * 360.0) / self._steps_per_revolution

    def _degrees_per_second_to_step_hz(self, speed_deg_per_sec: float) -> float:
        return (speed_deg_per_sec * self._steps_per_revolution) / 360.0

    @staticmethod
    # Build a protocol-level ERR line instead of raising internally, matching firmware behavior.
    def _build_err(code: str, details: str) -> str:
        return f"ERR,{code},{details}"

    @staticmethod
    # Wrap angles into the controller's 0..360 representation.
    def _normalize_angle_360(angle_deg: float) -> float:
        wrapped = math.fmod(angle_deg, 360.0)
        if wrapped < 0.0:
            wrapped += 360.0
        if wrapped >= 360.0:
            wrapped -= 360.0
        return wrapped

    @staticmethod
    # Choose the shortest signed rotation from current to target.
    def _shortest_signed_delta_deg(current_deg: float, target_deg: float) -> float:
        delta = SimulatedControllerSerial._normalize_angle_360(target_deg - current_deg)
        if delta > 180.0:
            delta -= 360.0
        return delta

    @staticmethod
    # Force a clockwise-only solution for absolute moves when the command asks for CW.
    def _clockwise_delta_deg(current_deg: float, target_deg: float) -> float:
        return SimulatedControllerSerial._normalize_angle_360(target_deg - current_deg)

    @staticmethod
    # Force a counter-clockwise-only solution for absolute moves when the command asks for CCW.
    def _counter_clockwise_delta_deg(current_deg: float, target_deg: float) -> float:
        return -SimulatedControllerSerial._normalize_angle_360(current_deg - target_deg)

    @staticmethod
    # Match the firmware's signed rounding behavior when converting floating-point angles to integer steps.
    def _round_to_int32(value: float) -> int:
        return int(value + 0.5) if value >= 0.0 else int(value - 0.5)

    @staticmethod
    def _value_in_range(value: float, minimum: float, maximum: float) -> bool:
        return minimum <= value <= maximum

    @staticmethod
    # Parsing helpers reject malformed protocol fields the same way embedded code would.
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
    # Utility used when deciding whether to preserve the last motion direction for telemetry.
    def _is_motion_state(state: ControllerState) -> bool:
        return state in {
            ControllerState.MOVING_ABSOLUTE,
            ControllerState.MOVING_RELATIVE,
            ControllerState.CONSTANT_ROTATE,
            ControllerState.HOMING_MECHANICAL_ZERO,
            ControllerState.MOVING_TO_VIRTUAL_ZERO,
        }

    # Push one ASCII line into the simulated RX queue so the manager reads it like serial input.
    def _enqueue_line(self, line: str) -> None:
        self._outbound_lines.put(f"{line}\r\n".encode("ascii"))


def build_simulated_serial_factory(config: SimulatorConfig | None = None):
    # Snapshot the config so each created simulator starts from a clean, predictable state.
    config_snapshot = deepcopy(config) if config is not None else SimulatorConfig()

    def factory(*, port: str, baudrate: int, timeout: float, write_timeout: float) -> SimulatedControllerSerial:
        # Hand each CommunicationManager its own isolated controller instance.
        return SimulatedControllerSerial(
            port=port,
            baudrate=baudrate,
            timeout=timeout,
            write_timeout=write_timeout,
            config=deepcopy(config_snapshot),
        )

    return factory
