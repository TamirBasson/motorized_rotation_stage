import threading
import time
import unittest

from pc_app.api.rotation_stage_api import RotationStageAPI
from pc_app.comm.communication_manager import CommunicationManager, DeviceErrorResponse
from pc_app.comm.models import MotionDirection, TelemetryState
from pc_app.sim import SimulatorConfig, build_simulated_serial_factory


class ControllerSimulatorIntegrationTests(unittest.TestCase):
    def test_motion_is_gradual_and_telemetry_streams_while_running(self) -> None:
        api = RotationStageAPI.from_simulator(port="SIM_GRADUAL_TEST", read_timeout=0.01)
        received: list[TelemetryState] = []
        enough_updates = threading.Event()

        def handle_telemetry(telemetry: TelemetryState) -> None:
            received.append(telemetry)
            if len(received) >= 4:
                enough_updates.set()

        api.start()
        subscription = api.subscribe_telemetry(handle_telemetry, replay_latest=False)
        try:
            api.set_telemetry_rate(20)
            api.rotate_relative(delta_angle_deg=20.0, speed_deg_per_sec=10.0)

            self.assertTrue(enough_updates.wait(timeout=1.5), "Expected multiple telemetry updates during motion")
            self.assertTrue(any(sample.running for sample in received), "Telemetry never reported active motion")
            self.assertTrue(
                any(0.1 < sample.mechanical_angle_deg < 19.9 for sample in received),
                "Motion appears to jump directly to the final position",
            )

            step_history = [sample.steps for sample in received]
            self.assertTrue(step_history[-1] > step_history[0], "Step count did not advance during motion")

            final = _wait_for_telemetry(lambda sample: not sample.running, api=api, timeout=3.0)
            self.assertAlmostEqual(final.mechanical_angle_deg, 20.0, delta=0.25)
        finally:
            subscription.unsubscribe()
            api.stop()

    def test_command_override_stop_and_direction_reporting(self) -> None:
        api = RotationStageAPI.from_simulator(port="SIM_OVERRIDE_TEST", read_timeout=0.01)
        api.start()
        try:
            api.set_telemetry_rate(25)
            api.constant_rotate(speed_deg_per_sec=5.0, direction="CW")
            running_cw = _wait_for_telemetry(
                lambda sample: sample.running and sample.direction == MotionDirection.CW and sample.steps > 0,
                api=api,
            )
            self.assertTrue(running_cw.running)

            api.rotate_relative(delta_angle_deg=-15.0, speed_deg_per_sec=10.0)
            running_ccw = _wait_for_telemetry(
                lambda sample: sample.running and sample.direction == MotionDirection.CCW,
                api=api,
            )
            self.assertEqual(running_ccw.direction, MotionDirection.CCW)

            api.stop_rotation()
            stopped = _wait_for_telemetry(lambda sample: not sample.running, api=api)
            self.assertFalse(stopped.running)
            self.assertEqual(stopped.direction, MotionDirection.CCW)
        finally:
            api.stop()

    def test_home_virtual_zero_and_immediate_telemetry(self) -> None:
        api = RotationStageAPI.from_simulator(
            port="SIM_HOME_TEST",
            read_timeout=0.01,
            simulator_config=SimulatorConfig(initial_steps=900, default_seek_speed_deg_per_sec=10.0),
        )
        api.start()
        try:
            api.set_telemetry_rate(-1)
            initial = _wait_for_telemetry(lambda sample: sample is not None, api=api)
            self.assertAlmostEqual(initial.mechanical_angle_deg, 9.0, delta=0.25)

            api.set_telemetry_rate(20)
            api.rotate_mechanical_zero()
            homed = _wait_for_telemetry(lambda sample: not sample.running and sample.steps == 0, api=api, timeout=3.0)
            self.assertAlmostEqual(homed.mechanical_angle_deg, 0.0, delta=0.25)

            api.rotate_virtual_zero(15.0)
            virtual_zero = _wait_for_telemetry(
                lambda sample: (
                    not sample.running
                    and abs(sample.virtual_angle_deg) < 0.25
                    and abs(sample.mechanical_angle_deg - 15.0) < 0.25
                ),
                api=api,
                timeout=3.0,
            )
            self.assertAlmostEqual(virtual_zero.mechanical_angle_deg, 15.0, delta=0.25)
        finally:
            api.stop()

    def test_invalid_command_returns_protocol_error_response(self) -> None:
        manager = CommunicationManager(
            port="SIM_ERR_TEST",
            read_timeout=0.01,
            serial_factory=build_simulated_serial_factory(),
        )
        manager.start()
        try:
            with self.assertRaises(DeviceErrorResponse) as context:
                manager.send_command("CMD,ROT_CONST,30.0,CW", timeout=1.0)
        finally:
            manager.stop()

        self.assertEqual(context.exception.error.error_code, "PARAM_OUT_OF_RANGE")
        self.assertEqual(context.exception.error.details, "ROT_CONST")


def _wait_for_telemetry(
    predicate,
    *,
    api: RotationStageAPI,
    timeout: float = 1.5,
    poll_interval: float = 0.01,
) -> TelemetryState:
    deadline = time.monotonic() + timeout
    last_sample: TelemetryState | None = None
    while time.monotonic() < deadline:
        sample = api.get_latest_telemetry()
        if sample is not None:
            last_sample = sample
            if predicate(sample):
                return sample
        time.sleep(poll_interval)

    raise AssertionError(f"Telemetry condition was not met within {timeout:.2f}s; last sample={last_sample!r}")


if __name__ == "__main__":
    unittest.main()
