import threading
import time
import unittest
from unittest.mock import patch

import pc_app.comm.communication_manager as communication_manager_module
from pc_app.api.rotation_stage_api import RotationStageAPI
from pc_app.comm.communication_manager import CommunicationManager
from pc_app.comm.models import MotionDirection, TelemetryState


class _MockSerial:
    def __init__(self, inbound_lines: list[bytes], *, read_timeout: float, event_log: list[tuple[str, int, str]]) -> None:
        self._inbound_lines = list(inbound_lines)
        self._read_timeout = read_timeout
        self._event_log = event_log
        self._lock = threading.Lock()
        self._closed = False
        self.nonempty_read_count = 0
        self.writes: list[bytes] = []

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
        self.writes.append(payload)
        return len(payload)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        with self._lock:
            self._closed = True


class _SerialModuleStub:
    def __init__(self, serial_instance: _MockSerial) -> None:
        self._serial_instance = serial_instance

    def Serial(self, *args, **kwargs) -> _MockSerial:
        return self._serial_instance


class CommunicationManagerFanoutTests(unittest.TestCase):
    def test_single_serial_read_fans_out_to_ui_and_api_near_realtime(self) -> None:
        event_log: list[tuple[str, int, str]] = []
        expected = TelemetryState(
            mechanical_angle_deg=123.45,
            virtual_angle_deg=110.95,
            running=True,
            speed_deg_per_sec=5.0,
            direction=MotionDirection.CW,
            steps=9876,
        )
        mock_serial = _MockSerial(
            [b"TLM,123.45,110.95,1,5.00,CW,9876\r\n"],
            read_timeout=0.005,
            event_log=event_log,
        )
        ui_received: list[TelemetryState] = []
        api_received: list[TelemetryState] = []
        ui_event = threading.Event()
        api_event = threading.Event()

        original_parse_message = communication_manager_module.parse_message

        def instrumented_parse_message(line: str):
            event_log.append(("telemetry_parsed", time.perf_counter_ns(), line.strip()))
            return original_parse_message(line)

        def ui_callback(telemetry: TelemetryState) -> None:
            event_log.append(("ui_forwarded", time.perf_counter_ns(), f"steps={telemetry.steps}"))
            ui_received.append(telemetry)
            ui_event.set()

        def api_callback(telemetry: TelemetryState) -> None:
            event_log.append(("api_forwarded", time.perf_counter_ns(), f"steps={telemetry.steps}"))
            api_received.append(telemetry)
            api_event.set()

        manager = CommunicationManager(port="MOCK_FANOUT_PORT", read_timeout=0.005)
        api = RotationStageAPI(manager)
        manager.subscribe_telemetry(ui_callback, replay_latest=False)
        api.subscribe_telemetry(api_callback, replay_latest=False)

        with patch.object(communication_manager_module, "serial", _SerialModuleStub(mock_serial)), patch.object(
            communication_manager_module,
            "parse_message",
            instrumented_parse_message,
        ):
            try:
                manager.start()
                self.assertTrue(ui_event.wait(timeout=1.0), "UI subscriber did not receive telemetry")
                self.assertTrue(api_event.wait(timeout=1.0), "API subscriber did not receive telemetry")
            finally:
                manager.stop()

        self.assertEqual(mock_serial.nonempty_read_count, 1)
        self.assertEqual(ui_received, [expected])
        self.assertEqual(api_received, [expected])
        self.assertEqual(manager.get_latest_telemetry(), expected)

        receive_ns = _get_event_time_ns(event_log, "serial_received")
        parsed_ns = _get_event_time_ns(event_log, "telemetry_parsed")
        ui_ns = _get_event_time_ns(event_log, "ui_forwarded")
        api_ns = _get_event_time_ns(event_log, "api_forwarded")

        self.assertGreaterEqual(parsed_ns, receive_ns)
        self.assertGreaterEqual(ui_ns, parsed_ns)
        self.assertGreaterEqual(api_ns, parsed_ns)

        # Local in-process fan-out should be effectively immediate.
        self.assertLess((ui_ns - receive_ns) / 1_000_000, 50.0)
        self.assertLess((api_ns - receive_ns) / 1_000_000, 50.0)


def _get_event_time_ns(events: list[tuple[str, int, str]], name: str) -> int:
    for event_name, timestamp_ns, _ in events:
        if event_name == name:
            return timestamp_ns
    raise AssertionError(f"Missing event {name!r} in log: {events!r}")


if __name__ == "__main__":
    unittest.main()
