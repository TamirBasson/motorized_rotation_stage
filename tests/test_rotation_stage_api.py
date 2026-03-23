import unittest
from unittest.mock import Mock

from pc_app.api.rotation_stage_api import RotationStageAPI
from pc_app.comm.models import AckMessage


class RotationStageApiTests(unittest.TestCase):
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
