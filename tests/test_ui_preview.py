import tkinter as tk
import unittest

from pc_app.comm.models import MotionDirection, TelemetryState
from pc_app.ui.preview_app import PreviewController
from pc_app.ui.telemetry_view import TelemetryView


class UiPreviewTests(unittest.TestCase):
    def test_preview_rotate_absolute_uses_virtual_reference_definition(self) -> None:
        controller = PreviewController()
        try:
            controller.rotate_absolute(120.0, -15.0, 5.0, "CW")
            telemetry = controller.get_latest_telemetry()
        finally:
            controller.shutdown()

        expected_mechanical = (120.0 + (-15.0)) % 360.0
        expected_virtual = (expected_mechanical - (-15.0)) % 360.0
        self.assertAlmostEqual(telemetry.mechanical_angle_deg, expected_mechanical)
        self.assertAlmostEqual(telemetry.virtual_angle_deg, expected_virtual)

    def test_preview_controller_updates_telemetry(self) -> None:
        controller = PreviewController()
        try:
            before = controller.get_latest_telemetry()
            controller.rotate_absolute(120.0, -15.0, 5.0, "CW")
            controller.rotate_relative(10.0, 3.0, "CW")
            after = controller.get_latest_telemetry()
        finally:
            controller.shutdown()

        self.assertFalse(before.running)
        self.assertTrue(after.running)
        self.assertEqual(after.direction, MotionDirection.CW)
        # Firmware convention: Virtual = Mechanical − Virtual Zero Reference (here reference = −15°).
        reference_deg = -15.0
        expected_virtual = (after.mechanical_angle_deg - reference_deg) % 360.0
        self.assertAlmostEqual(after.virtual_angle_deg, expected_virtual)

    def test_telemetry_view_renders_values(self) -> None:
        root = None
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

            descendants = list(_walk_widgets(view))
            labels = [
                child.cget("text")
                for child in descendants
                if hasattr(child, "cget") and child.winfo_class() == "TLabel"
            ]
            self.assertIn("Mechanical Degree", labels)

            rendered = [
                child.cget("text")
                for child in descendants
                if hasattr(child, "cget")
                and child.winfo_class() == "TLabel"
                and child.cget("text") in {"12.34", "56.78", "RUNNING", "4.50", "CCW", "321"}
            ]
            self.assertEqual(len(rendered), 6)
        finally:
            if root is not None:
                root.destroy()

def _walk_widgets(widget: tk.Misc):
    for child in widget.winfo_children():
        yield child
        yield from _walk_widgets(child)


if __name__ == "__main__":
    unittest.main()
