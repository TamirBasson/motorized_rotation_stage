from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from pc_app.ui.controller_interface import StageController


class ControlPanel(ttk.LabelFrame):
    def __init__(
        self,
        master: tk.Misc,
        controller: StageController,
        status_callback: Callable[[str], None],
    ) -> None:
        super().__init__(master, text="Controls")
        self._controller = controller
        self._status_callback = status_callback

        self._abs_angle = tk.StringVar(value="120.0")
        self._abs_offset = tk.StringVar(value="-15.0")
        self._abs_speed = tk.StringVar(value="5.0")
        self._abs_direction = tk.StringVar(value="CW")

        self._const_speed = tk.StringVar(value="2.5")
        self._const_direction = tk.StringVar(value="CCW")

        self._rel_delta = tk.StringVar(value="-45.0")
        self._rel_speed = tk.StringVar(value="3.0")

        self._vzero_offset = tk.StringVar(value="-12.5")
        self._telemetry_rate = tk.StringVar(value="2")

        self._build()

    def _build(self) -> None:
        self._add_labeled_entry("Absolute angle", self._abs_angle, 0)
        self._add_labeled_entry("Absolute offset", self._abs_offset, 1)
        self._add_labeled_entry("Absolute speed", self._abs_speed, 2)
        self._add_labeled_combo("Absolute direction", self._abs_direction, ("CW", "CCW", "NULL"), 3)
        ttk.Button(self, text="Rotate Absolute", command=self._on_rotate_absolute).grid(
            row=4,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=8,
            pady=(0, 10),
        )

        self._add_labeled_entry("Constant speed", self._const_speed, 5)
        self._add_labeled_combo("Constant direction", self._const_direction, ("CW", "CCW"), 6)
        ttk.Button(self, text="Constant Rotate", command=self._on_constant_rotate).grid(
            row=7,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=8,
            pady=(0, 10),
        )

        self._add_labeled_entry("Relative delta", self._rel_delta, 8)
        self._add_labeled_entry("Relative speed", self._rel_speed, 9)
        ttk.Button(self, text="Rotate Relative", command=self._on_rotate_relative).grid(
            row=10,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=8,
            pady=(0, 10),
        )

        self._add_labeled_entry("Virtual zero offset", self._vzero_offset, 11)
        ttk.Button(self, text="Rotate Virtual Zero", command=self._on_rotate_virtual_zero).grid(
            row=12,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=8,
            pady=(0, 10),
        )

        self._add_labeled_entry("Telemetry rate", self._telemetry_rate, 13)
        ttk.Button(self, text="Set Telemetry Rate", command=self._on_set_telemetry_rate).grid(
            row=14,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=8,
            pady=(0, 10),
        )

        ttk.Button(self, text="Rotate Mechanical Zero", command=self._on_rotate_mechanical_zero).grid(
            row=15,
            column=0,
            sticky="ew",
            padx=(8, 4),
            pady=(0, 8),
        )
        ttk.Button(self, text="Stop", command=self._on_stop).grid(
            row=15,
            column=1,
            sticky="ew",
            padx=(4, 8),
            pady=(0, 8),
        )

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

    def _add_labeled_entry(self, label: str, variable: tk.StringVar, row: int) -> None:
        ttk.Label(self, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(self, textvariable=variable).grid(row=row, column=1, sticky="ew", padx=8, pady=4)

    def _add_labeled_combo(
        self,
        label: str,
        variable: tk.StringVar,
        values: tuple[str, ...],
        row: int,
    ) -> None:
        ttk.Label(self, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=4)
        ttk.Combobox(self, textvariable=variable, values=values, state="readonly").grid(
            row=row,
            column=1,
            sticky="ew",
            padx=8,
            pady=4,
        )

    def _run_action(self, action: Callable[[], object]) -> None:
        try:
            ack = action()
        except Exception as exc:
            self._status_callback(f"Error: {exc}")
            return
        self._status_callback(f"ACK: {getattr(ack, 'command_type', 'UNKNOWN')}")

    def _on_rotate_absolute(self) -> None:
        self._run_action(
            lambda: self._controller.rotate_absolute(
                angle_deg=float(self._abs_angle.get()),
                virt_zero_offset_deg=float(self._abs_offset.get()),
                speed_deg_per_sec=float(self._abs_speed.get()),
                direction=self._abs_direction.get(),
            )
        )

    def _on_constant_rotate(self) -> None:
        self._run_action(
            lambda: self._controller.constant_rotate(
                speed_deg_per_sec=float(self._const_speed.get()),
                direction=self._const_direction.get(),
            )
        )

    def _on_rotate_relative(self) -> None:
        self._run_action(
            lambda: self._controller.rotate_relative(
                delta_angle_deg=float(self._rel_delta.get()),
                speed_deg_per_sec=float(self._rel_speed.get()),
            )
        )

    def _on_rotate_virtual_zero(self) -> None:
        self._run_action(
            lambda: self._controller.rotate_virtual_zero(
                virt_zero_offset_deg=float(self._vzero_offset.get()),
            )
        )

    def _on_set_telemetry_rate(self) -> None:
        self._run_action(lambda: self._controller.set_telemetry_rate(rate_hz=int(self._telemetry_rate.get())))

    def _on_rotate_mechanical_zero(self) -> None:
        self._run_action(self._controller.rotate_mechanical_zero)

    def _on_stop(self) -> None:
        self._run_action(self._controller.stop_rotation)
