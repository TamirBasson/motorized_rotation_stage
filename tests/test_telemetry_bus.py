import unittest

from pc_app.comm.models import MotionDirection, TelemetryState
from pc_app.comm.telemetry_bus import TelemetryBus


class TelemetryBusTests(unittest.TestCase):
    def test_publish_reaches_multiple_subscribers(self) -> None:
        bus = TelemetryBus()
        received_by_first: list[TelemetryState] = []
        received_by_second: list[TelemetryState] = []

        bus.subscribe(received_by_first.append)
        bus.subscribe(received_by_second.append)

        sample = TelemetryState(
            mechanical_angle_deg=10.0,
            virtual_angle_deg=12.5,
            running=True,
            speed_deg_per_sec=2.0,
            direction=MotionDirection.CCW,
            steps=123,
        )
        bus.publish(sample)

        self.assertEqual(received_by_first, [sample])
        self.assertEqual(received_by_second, [sample])

    def test_unsubscribe_stops_delivery(self) -> None:
        bus = TelemetryBus()
        received: list[TelemetryState] = []
        subscription = bus.subscribe(received.append)
        subscription.unsubscribe()

        sample = TelemetryState(
            mechanical_angle_deg=1.0,
            virtual_angle_deg=1.5,
            running=False,
            speed_deg_per_sec=0.0,
            direction=MotionDirection.NONE,
            steps=0,
        )
        bus.publish(sample)

        self.assertEqual(received, [])

    def test_one_bad_subscriber_does_not_block_others(self) -> None:
        bus = TelemetryBus()
        received: list[TelemetryState] = []

        def fail(_: TelemetryState) -> None:
            raise RuntimeError("boom")

        bus.subscribe(fail)
        bus.subscribe(received.append)

        sample = TelemetryState(
            mechanical_angle_deg=2.0,
            virtual_angle_deg=3.0,
            running=True,
            speed_deg_per_sec=1.0,
            direction=MotionDirection.CW,
            steps=50,
        )
        with self.assertLogs("pc_app.comm.telemetry_bus", level="ERROR"):
            bus.publish(sample)

        self.assertEqual(received, [sample])


if __name__ == "__main__":
    unittest.main()
