import unittest
from unittest.mock import patch

from pc_app.api.rotation_stage_api import RotationStageAPI
from pc_app.comm.communication_manager import CommunicationError
from pc_app.comm.port_detection import (
    SerialPortCandidate,
    auto_detect_controller_port,
)


class PortDetectionTests(unittest.TestCase):
    def test_auto_detect_prefers_arduino_like_port(self) -> None:
        ports = [
            SerialPortCandidate(device="COM1", description="Bluetooth Link", manufacturer="Microsoft", hwid="BT"),
            SerialPortCandidate(
                device="COM7",
                description="USB-SERIAL CH340",
                manufacturer="wch.cn",
                hwid="USB VID:PID=1A86:7523",
            ),
        ]

        with patch("pc_app.comm.port_detection.list_serial_ports", return_value=ports):
            self.assertEqual(auto_detect_controller_port(), "COM7")

    def test_auto_detect_uses_only_available_port(self) -> None:
        ports = [
            SerialPortCandidate(device="COM4", description="Unknown Serial Device", manufacturer="", hwid=""),
        ]

        with patch("pc_app.comm.port_detection.list_serial_ports", return_value=ports):
            self.assertEqual(auto_detect_controller_port(), "COM4")

    def test_auto_detect_raises_when_multiple_ports_are_ambiguous(self) -> None:
        ports = [
            SerialPortCandidate(device="COM3", description="Unknown Serial Device", manufacturer="", hwid=""),
            SerialPortCandidate(device="COM4", description="Unknown Serial Device", manufacturer="", hwid=""),
        ]

        with patch("pc_app.comm.port_detection.list_serial_ports", return_value=ports):
            with self.assertRaises(CommunicationError):
                auto_detect_controller_port()

    def test_api_can_be_built_from_auto_detected_port(self) -> None:
        with patch("pc_app.api.rotation_stage_api.auto_detect_controller_port", return_value="COM9"):
            api = RotationStageAPI.from_auto_detected_port()

        self.assertEqual(api.communication_manager.port, "COM9")


if __name__ == "__main__":
    unittest.main()
