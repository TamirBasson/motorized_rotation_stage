import threading
import time
import unittest

from pc_app.api.rotation_stage_api import RotationStageAPI
from pc_app.comm.models import TelemetryState
from pc_app.comm.remote_client import CommandQueuedError, RemoteCommunicationClient
from pc_app.comm.remote_server import RemoteCommunicationServer


class RemoteServerTests(unittest.TestCase):
    def test_shared_server_fans_out_telemetry_to_ui_and_api_clients(self) -> None:
        server = RemoteCommunicationServer.from_simulator(server_port=0)
        ui_api = RotationStageAPI(
            RemoteCommunicationClient(
                host=server.host,
                port=0,
                client_type="ui",
                client_name="UI Test",
                connect_timeout=2.0,
            )
        )
        api = RotationStageAPI.from_server(
            host=server.host,
            port=0,
            client_name="API Test",
            connect_timeout=2.0,
        )

        ui_received: list[TelemetryState] = []
        api_received: list[TelemetryState] = []
        ui_event = threading.Event()
        api_event = threading.Event()
        ui_subscription = None
        api_subscription = None

        try:
            server.start()
            ui_api = RotationStageAPI(
                RemoteCommunicationClient(
                    host=server.host,
                    port=server.port,
                    client_type="ui",
                    client_name="UI Test",
                    connect_timeout=2.0,
                )
            )
            api = RotationStageAPI.from_server(
                host=server.host,
                port=server.port,
                client_name="API Test",
                connect_timeout=2.0,
            )
            ui_api.start()
            api.start()
            ui_subscription = ui_api.subscribe_telemetry(lambda telemetry: _record(ui_received, telemetry, ui_event))
            api_subscription = api.subscribe_telemetry(lambda telemetry: _record(api_received, telemetry, api_event))
            api.set_telemetry_rate(10)

            self.assertTrue(ui_event.wait(timeout=2.0))
            self.assertTrue(api_event.wait(timeout=2.0))
            self.assertGreaterEqual(len(ui_received), 1)
            self.assertGreaterEqual(len(api_received), 1)
            self.assertIsNotNone(ui_api.get_latest_telemetry())
            self.assertIsNotNone(api.get_latest_telemetry())
        finally:
            try:
                if ui_subscription is not None:
                    ui_subscription.unsubscribe()
            except Exception:
                pass
            try:
                if api_subscription is not None:
                    api_subscription.unsubscribe()
            except Exception:
                pass
            ui_api.stop()
            api.stop()
            server.stop()

    def test_ui_commands_queue_until_api_releases_control(self) -> None:
        server = RemoteCommunicationServer.from_simulator(server_port=0)
        ui_api = RotationStageAPI(
            RemoteCommunicationClient(
                host=server.host,
                port=0,
                client_type="ui",
                client_name="UI Queue Test",
                connect_timeout=2.0,
            )
        )
        api = RotationStageAPI.from_server(
            host=server.host,
            port=0,
            client_name="API Queue Test",
            auto_acquire_control=True,
            connect_timeout=2.0,
        )

        try:
            server.start()
            ui_api = RotationStageAPI(
                RemoteCommunicationClient(
                    host=server.host,
                    port=server.port,
                    client_type="ui",
                    client_name="UI Queue Test",
                    connect_timeout=2.0,
                )
            )
            api = RotationStageAPI.from_server(
                host=server.host,
                port=server.port,
                client_name="API Queue Test",
                auto_acquire_control=True,
                connect_timeout=2.0,
            )
            ui_api.start()
            api.start()
            api.set_telemetry_rate(10)
            initial = _wait_for_telemetry(api)

            with self.assertRaises(CommandQueuedError):
                ui_api.rotate_relative(delta_angle_deg=45.0, speed_deg_per_sec=3.0, direction="CW")

            time.sleep(0.2)
            before_release = api.get_latest_telemetry()
            self.assertEqual(before_release, initial)

            api.release_control()
            updated = _wait_for_telemetry_change(api, previous_steps=initial.steps)
            self.assertNotEqual(updated.steps, initial.steps)
        finally:
            ui_api.stop()
            api.stop()
            server.stop()

    def test_ui_stop_bypasses_api_queue(self) -> None:
        server = RemoteCommunicationServer.from_simulator(server_port=0)
        ui_api = RotationStageAPI(
            RemoteCommunicationClient(
                host=server.host,
                port=0,
                client_type="ui",
                client_name="UI Stop Test",
                connect_timeout=2.0,
            )
        )
        api = RotationStageAPI.from_server(
            host=server.host,
            port=0,
            client_name="API Stop Test",
            auto_acquire_control=True,
            connect_timeout=2.0,
        )

        try:
            server.start()
            ui_api = RotationStageAPI(
                RemoteCommunicationClient(
                    host=server.host,
                    port=server.port,
                    client_type="ui",
                    client_name="UI Stop Test",
                    connect_timeout=2.0,
                )
            )
            api = RotationStageAPI.from_server(
                host=server.host,
                port=server.port,
                client_name="API Stop Test",
                auto_acquire_control=True,
                connect_timeout=2.0,
            )
            ui_api.start()
            api.start()
            api.set_telemetry_rate(10)
            api.constant_rotate(speed_deg_per_sec=2.5, direction="CW")
            running = _wait_for_running(api, expected=True)
            self.assertTrue(running.running)

            stop_ack = ui_api.stop_rotation()
            self.assertEqual(stop_ack.command_type, "STOP")
            stopped = _wait_for_running(api, expected=False)
            self.assertFalse(stopped.running)
        finally:
            ui_api.stop()
            api.stop()
            server.stop()


def _record(bucket: list[TelemetryState], telemetry: TelemetryState, event: threading.Event) -> None:
    bucket.append(telemetry)
    event.set()


def _wait_for_telemetry(api: RotationStageAPI, *, timeout: float = 2.0) -> TelemetryState:
    deadline = time.time() + timeout
    while time.time() < deadline:
        telemetry = api.get_latest_telemetry()
        if telemetry is not None:
            return telemetry
        time.sleep(0.02)
    raise AssertionError("Timed out waiting for telemetry")


def _wait_for_telemetry_change(
    api: RotationStageAPI,
    *,
    previous_steps: int,
    timeout: float = 2.0,
) -> TelemetryState:
    deadline = time.time() + timeout
    while time.time() < deadline:
        telemetry = api.get_latest_telemetry()
        if telemetry is not None and telemetry.steps != previous_steps:
            return telemetry
        time.sleep(0.02)
    raise AssertionError("Timed out waiting for telemetry change")


def _wait_for_running(api: RotationStageAPI, *, expected: bool, timeout: float = 2.0) -> TelemetryState:
    deadline = time.time() + timeout
    while time.time() < deadline:
        telemetry = api.get_latest_telemetry()
        if telemetry is not None and telemetry.running == expected:
            return telemetry
        time.sleep(0.02)
    raise AssertionError(f"Timed out waiting for running={expected}")


if __name__ == "__main__":
    unittest.main()
