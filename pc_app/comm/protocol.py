from __future__ import annotations

from typing import Final

from pc_app.comm.models import AckMessage, ErrMessage, MotionDirection, ParsedInboundMessage, TelemetryState


class ProtocolError(ValueError):
    """Raised when an inbound or outbound protocol message is invalid."""


ACK_FIELD_COUNTS: Final[dict[str, int]] = {
    "ROT_ABS": 6,
    "ROT_CONST": 4,
    "ROT_REL": 5,
    "ROT_HOME": 2,
    "ROT_VZERO": 3,
    "STOP": 2,
    "TLM": 3,
}

ERR_FIELD_COUNT: Final[int] = 3
TLM_FIELD_COUNT: Final[int] = 7


def parse_message(line: str) -> ParsedInboundMessage:
    """Parse a single inbound protocol line."""
    normalized = line.strip()
    if not normalized:
        raise ProtocolError("Empty protocol line")

    parts = normalized.split(",")
    family = parts[0]

    if family == "ACK":
        return _parse_ack(parts)
    if family == "ERR":
        return _parse_err(parts)
    if family == "TLM":
        return _parse_tlm(parts)
    raise ProtocolError(f"Unsupported message family: {family}")


def build_rotate_absolute_command(
    angle_deg: float,
    virt_zero_offset_deg: float,
    speed_deg_per_sec: float,
    direction: str,
) -> str:
    _validate_range("angle_deg", angle_deg, 0.0, 360.0)
    _validate_range("virt_zero_offset_deg", virt_zero_offset_deg, -180.0, 180.0)
    _validate_range("speed_deg_per_sec", speed_deg_per_sec, 0.1, 20.0)
    _validate_direction(direction, allowed={"CW", "CCW"})
    return ",".join(
        [
            "CMD",
            "ROT_ABS",
            _format_float(angle_deg),
            _format_float(virt_zero_offset_deg),
            _format_float(speed_deg_per_sec),
            direction,
        ]
    )


def build_constant_rotate_command(speed_deg_per_sec: float, direction: str) -> str:
    _validate_range("speed_deg_per_sec", speed_deg_per_sec, 0.1, 20.0)
    _validate_direction(direction, allowed={"CW", "CCW"})
    return ",".join(["CMD", "ROT_CONST", _format_float(speed_deg_per_sec), direction])


def build_rotate_relative_command(delta_angle_deg: float, speed_deg_per_sec: float, direction: str) -> str:
    _validate_range("delta_angle_deg", delta_angle_deg, 0.0, 360.0)
    _validate_range("speed_deg_per_sec", speed_deg_per_sec, 0.1, 20.0)
    _validate_direction(direction, allowed={"CW", "CCW"})
    return ",".join(["CMD", "ROT_REL", _format_float(delta_angle_deg), _format_float(speed_deg_per_sec), direction])


def build_rotate_home_command() -> str:
    return "CMD,ROT_HOME"


def build_rotate_virtual_zero_command(virt_zero_offset_deg: float) -> str:
    _validate_range("virt_zero_offset_deg", virt_zero_offset_deg, -180.0, 180.0)
    return ",".join(["CMD", "ROT_VZERO", _format_float(virt_zero_offset_deg)])


def build_stop_command() -> str:
    return "CMD,STOP"


def build_set_telemetry_rate_command(rate_hz: int) -> str:
    if rate_hz not in {-1, 0} and not 1 <= rate_hz <= 100:
        raise ProtocolError("rate_hz must be -1, 0, or 1..100")
    return f"CMD,TLM,{rate_hz}"


def _parse_ack(parts: list[str]) -> AckMessage:
    if len(parts) < 2:
        raise ProtocolError("ACK must contain at least a command type")

    command_type = parts[1]
    expected_fields = ACK_FIELD_COUNTS.get(command_type)
    if expected_fields is None:
        raise ProtocolError(f"Unsupported ACK command type: {command_type}")
    if len(parts) != expected_fields:
        raise ProtocolError(
            f"ACK for {command_type} must contain {expected_fields} fields, got {len(parts)}"
        )
    return AckMessage(command_type=command_type, parameters=tuple(parts[2:]))


def _parse_err(parts: list[str]) -> ErrMessage:
    if len(parts) != ERR_FIELD_COUNT:
        raise ProtocolError(f"ERR must contain {ERR_FIELD_COUNT} fields, got {len(parts)}")

    error_code = parts[1]
    if not error_code:
        raise ProtocolError("ERR error_code field may not be empty")

    details = parts[2]
    if not details:
        raise ProtocolError("ERR details field may not be empty")

    return ErrMessage(error_code=error_code, details=details)


def _parse_tlm(parts: list[str]) -> TelemetryState:
    if len(parts) != TLM_FIELD_COUNT:
        raise ProtocolError(f"TLM must contain {TLM_FIELD_COUNT} fields, got {len(parts)}")

    mechanical_angle_deg = _parse_float(parts[1], "mechanical_angle_deg")
    virtual_angle_deg = _parse_float(parts[2], "virtual_angle_deg")
    running_raw = parts[3]
    if running_raw not in {"0", "1"}:
        raise ProtocolError("TLM running field must be 0 or 1")

    speed_deg_per_sec = _parse_float(parts[4], "speed_deg_per_sec")
    direction = _parse_tlm_direction(parts[5])
    steps = _parse_int(parts[6], "steps")

    return TelemetryState(
        mechanical_angle_deg=mechanical_angle_deg,
        virtual_angle_deg=virtual_angle_deg,
        running=running_raw == "1",
        speed_deg_per_sec=speed_deg_per_sec,
        direction=direction,
        steps=steps,
    )


def _parse_tlm_direction(raw_value: str) -> MotionDirection:
    if raw_value == MotionDirection.CW.value:
        return MotionDirection.CW
    if raw_value == MotionDirection.CCW.value:
        return MotionDirection.CCW
    raise ProtocolError("TLM direction must be CW or CCW")


def _parse_float(value: str, field_name: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise ProtocolError(f"{field_name} must be a float") from exc


def _parse_int(value: str, field_name: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ProtocolError(f"{field_name} must be an integer") from exc


def _validate_range(field_name: str, value: float, minimum: float, maximum: float) -> None:
    if not minimum <= value <= maximum:
        raise ProtocolError(f"{field_name} must be within [{minimum}, {maximum}]")


def _validate_direction(direction: str, allowed: set[str]) -> None:
    if direction not in allowed:
        allowed_values = ", ".join(sorted(allowed))
        raise ProtocolError(f"direction must be one of: {allowed_values}")


def _format_float(value: float) -> str:
    return f"{value:.2f}"
