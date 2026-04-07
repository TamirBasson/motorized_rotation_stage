from __future__ import annotations

import json
from typing import Any

from pc_app.comm.models import AckMessage, ErrMessage, MotionDirection, TelemetryState


def encode_message(message: dict[str, Any]) -> bytes:
    return (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")


def decode_message(raw_line: str) -> dict[str, Any]:
    message = json.loads(raw_line)
    if not isinstance(message, dict):
        raise ValueError("Remote protocol messages must be JSON objects")
    return message


def serialize_ack(message: AckMessage) -> dict[str, Any]:
    return {
        "command_type": message.command_type,
        "parameters": list(message.parameters),
    }


def deserialize_ack(payload: dict[str, Any]) -> AckMessage:
    return AckMessage(
        command_type=str(payload["command_type"]),
        parameters=tuple(str(parameter) for parameter in payload.get("parameters", [])),
    )


def serialize_err(message: ErrMessage) -> dict[str, Any]:
    return {
        "error_code": message.error_code,
        "details": message.details,
    }


def deserialize_err(payload: dict[str, Any]) -> ErrMessage:
    return ErrMessage(
        error_code=str(payload["error_code"]),
        details=str(payload["details"]),
    )


def serialize_telemetry(message: TelemetryState) -> dict[str, Any]:
    return {
        "mechanical_angle_deg": message.mechanical_angle_deg,
        "virtual_angle_deg": message.virtual_angle_deg,
        "running": message.running,
        "speed_deg_per_sec": message.speed_deg_per_sec,
        "direction": message.direction.value,
        "steps": message.steps,
    }


def deserialize_telemetry(payload: dict[str, Any]) -> TelemetryState:
    return TelemetryState(
        mechanical_angle_deg=float(payload["mechanical_angle_deg"]),
        virtual_angle_deg=float(payload["virtual_angle_deg"]),
        running=bool(payload["running"]),
        speed_deg_per_sec=float(payload["speed_deg_per_sec"]),
        direction=MotionDirection(str(payload["direction"])),
        steps=int(payload["steps"]),
    )
