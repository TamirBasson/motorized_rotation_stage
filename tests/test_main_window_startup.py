import unittest

from pc_app.comm.models import MotionDirection, TelemetryState
from pc_app.ui.main_window import MainWindow


class MainWindowStartupTests(unittest.TestCase):
    def test_startup_homing_not_finished_without_telemetry(self) -> None:
        self.assertFalse(MainWindow._startup_homing_finished(None, homing_motion_seen=False))

    def test_startup_homing_waits_while_motion_is_running(self) -> None:
        telemetry = TelemetryState(
            mechanical_angle_deg=42.0,
            virtual_angle_deg=42.0,
            running=True,
            speed_deg_per_sec=5.0,
            direction=MotionDirection.CCW,
            steps=420,
        )
        self.assertFalse(MainWindow._startup_homing_finished(telemetry, homing_motion_seen=False))

    def test_startup_homing_finishes_after_motion_stops(self) -> None:
        telemetry = TelemetryState(
            mechanical_angle_deg=18.0,
            virtual_angle_deg=18.0,
            running=False,
            speed_deg_per_sec=0.0,
            direction=MotionDirection.CCW,
            steps=180,
        )
        self.assertTrue(MainWindow._startup_homing_finished(telemetry, homing_motion_seen=True))

    def test_startup_homing_accepts_already_homed_stage(self) -> None:
        telemetry = TelemetryState(
            mechanical_angle_deg=0.0,
            virtual_angle_deg=0.0,
            running=False,
            speed_deg_per_sec=0.0,
            direction=MotionDirection.CCW,
            steps=0,
        )
        self.assertTrue(MainWindow._startup_homing_finished(telemetry, homing_motion_seen=False))


if __name__ == "__main__":
    unittest.main()
