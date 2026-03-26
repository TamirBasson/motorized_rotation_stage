import unittest
from unittest.mock import Mock

from pc_app.api.rotation_stage_api import RotationStageAPI
from pc_app.comm.models import AckMessage


class RotationStageApiTests(unittest.TestCase):
    def test_rotate_relative_forwards_directional_command(self) -> None:
        manager = Mock()
        manager.send_command.return_value = AckMessage(command_type="ROT_REL", parameters=())
        api = RotationStageAPI(manager)

        api.rotate_relative(
            delta_angle_deg=45.0,
            speed_deg_per_sec=3.0,
            direction="CCW",
        )

        manager.send_command.assert_called_once_with("CMD,ROT_REL,45.00,3.00,CCW", timeout=1.0)

    def test_rotate_absolute_updates_virtual_zero_offset(self) -> None:
        manager = Mock()
        manager.send_command.return_value = AckMessage(command_type="ROT_ABS", parameters=())
        api = RotationStageAPI(manager)

        api.rotate_absolute(
            angle_deg=120.0,
            virt_zero_offset_deg=-12.5,
            speed_deg_per_sec=5.0,
            direction="CW",
        )

        self.assertEqual(api.get_virtual_zero_offset_deg(), -12.5)

    def test_rotate_virtual_zero_updates_virtual_zero_offset(self) -> None:
        manager = Mock()
        manager.send_command.return_value = AckMessage(command_type="ROT_VZERO", parameters=())
        api = RotationStageAPI(manager)

        api.rotate_virtual_zero(-7.5)

        self.assertEqual(api.get_virtual_zero_offset_deg(), -7.5)


if __name__ == "__main__":
    unittest.main()
