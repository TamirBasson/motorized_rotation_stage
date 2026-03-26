from __future__ import annotations

import threading
import time

from pc_app.comm.models import AckMessage, MotionDirection, TelemetryState
from pc_app.comm.telemetry_bus import TelemetryBus, TelemetryPriority, TelemetrySubscription
from pc_app.ui.main_window import MainWindow


class PreviewController:
    """In-memory controller used to preview the UI without hardware."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running = True
        self._telemetry_rate_hz = 5
        self._virtual_zero_offset_deg = -12.5
        self._telemetry_bus = TelemetryBus()
        self._telemetry = self._build_telemetry(
            mechanical_angle_deg=123.45,
            running=False,
            speed_deg_per_sec=0.0,
            direction=MotionDirection.CW,
            steps=9876,
        )
        self._thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self._thread.start()

    def shutdown(self) -> None:
        self._running = False
        self._thread.join(timeout=1.0)

    def rotate_absolute(
        self,
        angle_deg: float,
        virt_zero_offset_deg: float,
        speed_deg_per_sec: float,
        direction: str,
        *,
        timeout: float = 1.0,
    ) -> AckMessage:
        del timeout
        with self._lock:
            self._virtual_zero_offset_deg = virt_zero_offset_deg
            # Absolute commands are expressed in the virtual frame, so convert to the
            # corresponding mechanical target before updating preview telemetry.
            target_mechanical_deg = _normalize_angle_360(
                angle_deg + self._virtual_zero_offset_deg,
            )
            self._telemetry = self._build_telemetry(
                mechanical_angle_deg=target_mechanical_deg,
                running=True,
                speed_deg_per_sec=speed_deg_per_sec,
                direction=MotionDirection(direction),
                steps=self._telemetry.steps + 200,
            )
            telemetry = self._telemetry
        self._telemetry_bus.publish(telemetry)
        return AckMessage(command_type="ROT_ABS", parameters=(f"{angle_deg:.2f}", f"{virt_zero_offset_deg:.2f}"))

    def constant_rotate(self, speed_deg_per_sec: float, direction: str, *, timeout: float = 1.0) -> AckMessage:
        del timeout
        with self._lock:
            self._telemetry = self._build_telemetry(
                mechanical_angle_deg=self._telemetry.mechanical_angle_deg,
                running=True,
                speed_deg_per_sec=speed_deg_per_sec,
                direction=MotionDirection(direction),
                steps=self._telemetry.steps,
            )
            telemetry = self._telemetry
        self._telemetry_bus.publish(telemetry)
        return AckMessage(command_type="ROT_CONST", parameters=(f"{speed_deg_per_sec:.2f}", direction))

    def rotate_relative(
        self,
        delta_angle_deg: float,
        speed_deg_per_sec: float,
        direction: str,
        *,
        timeout: float = 1.0,
    ) -> AckMessage:
        del timeout
        with self._lock:
            motion_direction = MotionDirection(direction)
            signed_delta_deg = delta_angle_deg if motion_direction == MotionDirection.CW else -delta_angle_deg
            self._telemetry = self._build_telemetry(
                mechanical_angle_deg=self._telemetry.mechanical_angle_deg + signed_delta_deg,
                running=True,
                speed_deg_per_sec=speed_deg_per_sec,
                direction=motion_direction,
                steps=self._telemetry.steps + int(delta_angle_deg * 10),
            )
            telemetry = self._telemetry
        self._telemetry_bus.publish(telemetry)
        return AckMessage(
            command_type="ROT_REL",
            parameters=(f"{delta_angle_deg:.2f}", f"{speed_deg_per_sec:.2f}", direction),
        )

    def rotate_mechanical_zero(self, *, timeout: float = 1.0) -> AckMessage:
        del timeout
        with self._lock:
            self._telemetry = self._build_telemetry(
                mechanical_angle_deg=0.0,
                running=False,
                speed_deg_per_sec=0.0,
                direction=MotionDirection.CW,
                steps=0,
            )
            telemetry = self._telemetry
        self._telemetry_bus.publish(telemetry)
        return AckMessage(command_type="ROT_HOME", parameters=())

    def rotate_virtual_zero(self, virt_zero_offset_deg: float, *, timeout: float = 1.0) -> AckMessage:
        del timeout
        with self._lock:
            self._virtual_zero_offset_deg = virt_zero_offset_deg
            # Virtual = 0 when Mechanical equals the configured reference (firmware behavior).
            target_mechanical_deg = _normalize_angle_360(virt_zero_offset_deg)
            self._telemetry = self._build_telemetry(
                mechanical_angle_deg=target_mechanical_deg,
                running=True,
                speed_deg_per_sec=max(self._telemetry.speed_deg_per_sec, 1.0),
                direction=self._telemetry.direction,
                steps=self._telemetry.steps + 100,
            )
            telemetry = self._telemetry
        self._telemetry_bus.publish(telemetry)
        return AckMessage(command_type="ROT_VZERO", parameters=(f"{virt_zero_offset_deg:.2f}",))

    def stop_rotation(self, *, timeout: float = 1.0) -> AckMessage:
        del timeout
        with self._lock:
            self._telemetry = self._build_telemetry(
                mechanical_angle_deg=self._telemetry.mechanical_angle_deg,
                running=False,
                speed_deg_per_sec=0.0,
                direction=MotionDirection.CW,
                steps=self._telemetry.steps,
            )
            telemetry = self._telemetry
        self._telemetry_bus.publish(telemetry)
        return AckMessage(command_type="STOP", parameters=())

    def set_telemetry_rate(self, rate_hz: int, *, timeout: float = 1.0) -> AckMessage:
        del timeout
        with self._lock:
            self._telemetry_rate_hz = rate_hz
        return AckMessage(command_type="TLM", parameters=(str(rate_hz),))

    def get_latest_telemetry(self) -> TelemetryState:
        with self._lock:
            return self._telemetry

    def subscribe_telemetry(
        self,
        callback,
        *,
        replay_latest: bool = True,
        priority: TelemetryPriority = "high",
    ) -> TelemetrySubscription:
        subscription = self._telemetry_bus.subscribe(callback, priority=priority)
        if replay_latest:
            callback(self.get_latest_telemetry())
        return subscription

    def get_virtual_zero_offset_deg(self) -> float:
        with self._lock:
            return self._virtual_zero_offset_deg

    def _simulation_loop(self) -> None:
        while self._running:
            time.sleep(1.0 / self._telemetry_rate_hz)
            with self._lock:
                if not self._telemetry.running:
                    continue

                step_increment = max(int(self._telemetry.speed_deg_per_sec * 4), 1)
                direction_sign = 1 if self._telemetry.direction != MotionDirection.CCW else -1
                mechanical = (self._telemetry.mechanical_angle_deg + direction_sign * 0.5) % 360.0
                self._telemetry = self._build_telemetry(
                    mechanical_angle_deg=mechanical,
                    running=True,
                    speed_deg_per_sec=self._telemetry.speed_deg_per_sec,
                    direction=self._telemetry.direction,
                    steps=self._telemetry.steps + step_increment,
                )
                telemetry = self._telemetry
            self._telemetry_bus.publish(telemetry)

    def _build_telemetry(
        self,
        *,
        mechanical_angle_deg: float,
        running: bool,
        speed_deg_per_sec: float,
        direction: MotionDirection,
        steps: int,
    ) -> TelemetryState:
        normalized_mechanical = _normalize_angle_360(mechanical_angle_deg)
        # Matches firmware: Virtual = Mechanical − Virtual Zero Reference
        virtual_angle_deg = _normalize_angle_360(
            normalized_mechanical - self._virtual_zero_offset_deg,
        )
        return TelemetryState(
            mechanical_angle_deg=normalized_mechanical,
            virtual_angle_deg=virtual_angle_deg,
            running=running,
            speed_deg_per_sec=speed_deg_per_sec,
            direction=direction,
            steps=steps,
        )


def _normalize_angle_360(angle_deg: float) -> float:
    wrapped = angle_deg % 360.0
    if wrapped < 0.0:
        wrapped += 360.0
    if wrapped >= 360.0:
        wrapped -= 360.0
    return wrapped


def main() -> None:
    controller = PreviewController()
    window = MainWindow(controller)
    window.protocol("WM_DELETE_WINDOW", lambda: _close(window, controller))
    window.mainloop()


def _close(window: MainWindow, controller: PreviewController) -> None:
    window.shutdown()
    controller.shutdown()
    window.destroy()


if __name__ == "__main__":
    main()
