from __future__ import annotations

import threading
import time

from pc_app.comm.models import AckMessage, MotionDirection, TelemetryState
from pc_app.ui.main_window import MainWindow


class PreviewController:
    """In-memory controller used to preview the UI without hardware."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running = True
        self._telemetry_rate_hz = 5
        self._virtual_zero_offset_deg = -12.5
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
            self._telemetry = self._build_telemetry(
                mechanical_angle_deg=angle_deg,
                running=True,
                speed_deg_per_sec=speed_deg_per_sec,
                direction=MotionDirection(direction),
                steps=self._telemetry.steps + 200,
            )
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
        return AckMessage(command_type="ROT_CONST", parameters=(f"{speed_deg_per_sec:.2f}", direction))

    def rotate_relative(self, delta_angle_deg: float, speed_deg_per_sec: float, *, timeout: float = 1.0) -> AckMessage:
        del timeout
        with self._lock:
            direction = MotionDirection.CW if delta_angle_deg >= 0 else MotionDirection.CCW
            self._telemetry = self._build_telemetry(
                mechanical_angle_deg=self._telemetry.mechanical_angle_deg + delta_angle_deg,
                running=True,
                speed_deg_per_sec=speed_deg_per_sec,
                direction=direction,
                steps=self._telemetry.steps + int(abs(delta_angle_deg) * 10),
            )
        return AckMessage(command_type="ROT_REL", parameters=(f"{delta_angle_deg:.2f}", f"{speed_deg_per_sec:.2f}"))

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
        return AckMessage(command_type="ROT_HOME", parameters=())

    def rotate_virtual_zero(self, virt_zero_offset_deg: float, *, timeout: float = 1.0) -> AckMessage:
        del timeout
        with self._lock:
            self._virtual_zero_offset_deg = virt_zero_offset_deg
            target_mechanical_deg = (-virt_zero_offset_deg) % 360.0
            self._telemetry = self._build_telemetry(
                mechanical_angle_deg=target_mechanical_deg,
                running=True,
                speed_deg_per_sec=max(self._telemetry.speed_deg_per_sec, 1.0),
                direction=self._telemetry.direction,
                steps=self._telemetry.steps + 100,
            )
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
        return AckMessage(command_type="STOP", parameters=())

    def set_telemetry_rate(self, rate_hz: int, *, timeout: float = 1.0) -> AckMessage:
        del timeout
        with self._lock:
            self._telemetry_rate_hz = rate_hz
        return AckMessage(command_type="TLM", parameters=(str(rate_hz),))

    def get_latest_telemetry(self) -> TelemetryState:
        with self._lock:
            return self._telemetry

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

    def _build_telemetry(
        self,
        *,
        mechanical_angle_deg: float,
        running: bool,
        speed_deg_per_sec: float,
        direction: MotionDirection,
        steps: int,
    ) -> TelemetryState:
        normalized_mechanical = mechanical_angle_deg % 360.0
        virtual_angle_deg = (normalized_mechanical + self._virtual_zero_offset_deg) % 360.0
        return TelemetryState(
            mechanical_angle_deg=normalized_mechanical,
            virtual_angle_deg=virtual_angle_deg,
            running=running,
            speed_deg_per_sec=speed_deg_per_sec,
            direction=direction,
            steps=steps,
        )


def main() -> None:
    controller = PreviewController()
    window = MainWindow(controller)
    window.protocol("WM_DELETE_WINDOW", lambda: _close(window, controller))
    window.mainloop()


def _close(window: MainWindow, controller: PreviewController) -> None:
    controller.shutdown()
    window.destroy()


if __name__ == "__main__":
    main()
