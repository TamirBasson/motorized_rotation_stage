from __future__ import annotations

from pathlib import Path
import sys
import threading
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pc_app.comm.communication_manager as communication_manager_module
from pc_app.api.rotation_stage_api import RotationStageAPI
from pc_app.comm.communication_manager import CommunicationManager
from pc_app.comm.models import TelemetryState


class MockSerial:
    def __init__(self, inbound_lines: list[bytes], *, read_timeout: float, event_log: list[tuple[str, int, str]]) -> None:
        self._inbound_lines = list(inbound_lines)
        self._read_timeout = read_timeout
        self._event_log = event_log
        self._lock = threading.Lock()
        self._closed = False
        self.nonempty_read_count = 0

    def readline(self) -> bytes:
        with self._lock:
            if self._closed:
                return b""
            if self._inbound_lines:
                raw_line = self._inbound_lines.pop(0)
                self.nonempty_read_count += 1
                self._event_log.append(("serial_received", time.perf_counter_ns(), raw_line.decode("ascii").strip()))
                return raw_line

        time.sleep(self._read_timeout)
        return b""

    def write(self, payload: bytes) -> int:
        return len(payload)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        with self._lock:
            self._closed = True


class SerialModuleStub:
    def __init__(self, serial_instance: MockSerial) -> None:
        self._serial_instance = serial_instance

    def Serial(self, *args, **kwargs) -> MockSerial:
        return self._serial_instance


def main() -> None:
    event_log: list[tuple[str, int, str]] = []
    ui_event = threading.Event()
    api_event = threading.Event()

    original_parse_message = communication_manager_module.parse_message

    def instrumented_parse_message(line: str):
        event_log.append(("telemetry_parsed", time.perf_counter_ns(), line.strip()))
        return original_parse_message(line)

    def ui_callback(telemetry: TelemetryState) -> None:
        event_log.append(("ui_forwarded", time.perf_counter_ns(), _format_telemetry(telemetry)))
        ui_event.set()

    def api_callback(telemetry: TelemetryState) -> None:
        event_log.append(("api_forwarded", time.perf_counter_ns(), _format_telemetry(telemetry)))
        api_event.set()

    mock_serial = MockSerial(
        [b"TLM,123.45,110.95,1,5.00,CW,9876\r\n"],
        read_timeout=0.005,
        event_log=event_log,
    )
    manager = CommunicationManager(port="MOCK_FANOUT_PORT", read_timeout=0.005)
    api = RotationStageAPI(manager)

    manager.subscribe_telemetry(ui_callback, replay_latest=False)
    api.subscribe_telemetry(api_callback, replay_latest=False)

    with patch.object(communication_manager_module, "serial", SerialModuleStub(mock_serial)), patch.object(
        communication_manager_module,
        "parse_message",
        instrumented_parse_message,
    ):
        try:
            manager.start()
            if not ui_event.wait(timeout=1.0):
                raise RuntimeError("UI subscriber did not receive telemetry")
            if not api_event.wait(timeout=1.0):
                raise RuntimeError("API subscriber did not receive telemetry")
        finally:
            manager.stop()

    base_ns = min(timestamp_ns for _, timestamp_ns, _ in event_log)
    print("Telemetry fan-out demo")
    print("====================")
    print("Serial owner:", manager.port)
    print("UI serial access:", "none")
    print("API serial access:", "none")
    print("Non-empty telemetry reads from serial:", mock_serial.nonempty_read_count)
    print()
    for event_name, timestamp_ns, details in event_log:
        elapsed_ms = (timestamp_ns - base_ns) / 1_000_000
        print(f"{elapsed_ms:8.3f} ms | {event_name:<16} | {details}")

    receive_ns = _get_event_time_ns(event_log, "serial_received")
    parsed_ns = _get_event_time_ns(event_log, "telemetry_parsed")
    ui_ns = _get_event_time_ns(event_log, "ui_forwarded")
    api_ns = _get_event_time_ns(event_log, "api_forwarded")

    print()
    print(f"Parse latency: {(parsed_ns - receive_ns) / 1_000_000:.3f} ms")
    print(f"UI fan-out latency: {(ui_ns - receive_ns) / 1_000_000:.3f} ms")
    print(f"API fan-out latency: {(api_ns - receive_ns) / 1_000_000:.3f} ms")
    print(f"UI/API skew: {abs(api_ns - ui_ns) / 1_000_000:.3f} ms")


def _format_telemetry(telemetry: TelemetryState) -> str:
    return (
        f"mech={telemetry.mechanical_angle_deg:.2f}, "
        f"virt={telemetry.virtual_angle_deg:.2f}, "
        f"running={int(telemetry.running)}, "
        f"speed={telemetry.speed_deg_per_sec:.2f}, "
        f"dir={telemetry.direction.value}, "
        f"steps={telemetry.steps}"
    )


def _get_event_time_ns(events: list[tuple[str, int, str]], name: str) -> int:
    for event_name, timestamp_ns, _ in events:
        if event_name == name:
            return timestamp_ns
    raise RuntimeError(f"Missing event {name!r}")


if __name__ == "__main__":
    main()
