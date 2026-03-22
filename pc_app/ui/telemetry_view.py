from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from pc_app.comm.models import TelemetryState


class TelemetryView(ttk.LabelFrame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, text="Telemetry")
        self._values: dict[str, tk.StringVar] = {
            "mechanical_angle_deg": tk.StringVar(value="--"),
            "virtual_angle_deg": tk.StringVar(value="--"),
            "running": tk.StringVar(value="--"),
            "speed_deg_per_sec": tk.StringVar(value="--"),
            "direction": tk.StringVar(value="--"),
            "steps": tk.StringVar(value="--"),
        }

        rows = [
            ("Mechanical Angle (deg)", "mechanical_angle_deg"),
            ("Virtual Angle (deg)", "virtual_angle_deg"),
            ("Running", "running"),
            ("Speed (deg/s)", "speed_deg_per_sec"),
            ("Direction", "direction"),
            ("Steps", "steps"),
        ]
        for row_index, (label_text, key) in enumerate(rows):
            ttk.Label(self, text=label_text).grid(row=row_index, column=0, sticky="w", padx=8, pady=4)
            ttk.Label(self, textvariable=self._values[key], width=16).grid(
                row=row_index,
                column=1,
                sticky="e",
                padx=8,
                pady=4,
            )

        self.columnconfigure(0, weight=1)

    def update_telemetry(self, telemetry: TelemetryState | None) -> None:
        if telemetry is None:
            for value in self._values.values():
                value.set("--")
            return

        self._values["mechanical_angle_deg"].set(f"{telemetry.mechanical_angle_deg:.2f}")
        self._values["virtual_angle_deg"].set(f"{telemetry.virtual_angle_deg:.2f}")
        self._values["running"].set("Yes" if telemetry.running else "No")
        self._values["speed_deg_per_sec"].set(f"{telemetry.speed_deg_per_sec:.2f}")
        self._values["direction"].set(telemetry.direction.value)
        self._values["steps"].set(str(telemetry.steps))
