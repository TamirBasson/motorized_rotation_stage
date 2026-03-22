import unittest

from pc_app.comm.models import AckMessage, ErrMessage, MotionDirection, TelemetryState
from pc_app.comm.protocol import (
    ProtocolError,
    build_rotate_absolute_command,
    build_set_telemetry_rate_command,
    parse_message,
)


class ProtocolParserTests(unittest.TestCase):
    def test_parse_ack(self) -> None:
        message = parse_message("ACK,ROT_HOME")
        self.assertEqual(message, AckMessage(command_type="ROT_HOME", parameters=()))

    def test_parse_err(self) -> None:
        message = parse_message("ERR,UNKNOWN_COMMAND,CMD_XYZ")
        self.assertEqual(message, ErrMessage(error_code="UNKNOWN_COMMAND", details="CMD_XYZ"))

    def test_parse_unknown_err_code(self) -> None:
        message = parse_message("ERR,FIRMWARE_SPECIFIC,extra")
        self.assertEqual(message, ErrMessage(error_code="FIRMWARE_SPECIFIC", details="extra"))

    def test_parse_telemetry(self) -> None:
        message = parse_message("TLM,123.45,110.95,1,5.00,CW,9876")
        self.assertEqual(
            message,
            TelemetryState(
                mechanical_angle_deg=123.45,
                virtual_angle_deg=110.95,
                running=True,
                speed_deg_per_sec=5.0,
                direction=MotionDirection.CW,
                steps=9876,
            ),
        )

    def test_reject_invalid_telemetry_direction(self) -> None:
        with self.assertRaises(ProtocolError):
            parse_message("TLM,123.45,110.95,1,5.00,NULL,9876")

    def test_build_valid_commands(self) -> None:
        self.assertEqual(
            build_rotate_absolute_command(120.0, -15.0, 5.0, "CW"),
            "CMD,ROT_ABS,120.00,-15.00,5.00,CW",
        )
        self.assertEqual(build_set_telemetry_rate_command(10), "CMD,TLM,10")

    def test_reject_out_of_range_rate(self) -> None:
        with self.assertRaises(ProtocolError):
            build_set_telemetry_rate_command(101)


if __name__ == "__main__":
    unittest.main()
