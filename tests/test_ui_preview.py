import tkinter as tk
import unittest

from pc_app.comm.models import MotionDirection, TelemetryState
from pc_app.ui.preview_app import PreviewController
from pc_app.ui.telemetry_view import TelemetryView


class UiPreviewTests(unittest.TestCase):
    def test_preview_controller_updates_telemetry(self) -> None:
        controller = PreviewController()
        try:
            before = controller.get_latest_telemetry()
            controller.constant_rotate(2.0, "CW")
            controller.rotate_relative(10.0, 3.0)
            after = controller.get_latest_telemetry()
        finally:
            controller.shutdown()

        self.assertFalse(before.running)
        self.assertTrue(after.running)
        self.assertEqual(after.direction, MotionDirection.CW)

    def test_telemetry_view_renders_values(self) -> None:
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        try:
            root.withdraw()
            view = TelemetryView(root)
            sample = TelemetryState(
                mechanical_angle_deg=12.34,
                virtual_angle_deg=56.78,
                running=True,
                speed_deg_per_sec=4.5,
                direction=MotionDirection.CCW,
                steps=321,
            )
            view.update_telemetry(sample)

            labels = [
                child.cget("text")
                for child in view.winfo_children()
                if hasattr(child, "cget") and child.winfo_class() == "TLabel"
            ]
            self.assertIn("Mechanical Angle (deg)", labels)

            rendered = [
                child.cget("text")
                for child in view.winfo_children()
                if hasattr(child, "cget")
                and child.winfo_class() == "TLabel"
                and child.cget("text") in {"12.34", "56.78", "Yes", "4.50", "CCW", "321"}
            ]
            self.assertEqual(len(rendered), 6)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
