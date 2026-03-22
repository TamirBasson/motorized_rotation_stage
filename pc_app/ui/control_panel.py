from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from pc_app.ui.controller_interface import StageController


StatusCallback = Callable[[str, str, str], None]


class ControlPanel(ttk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        controller: StageController,
        status_callback: StatusCallback,
    ) -> None:
        super().__init__(master, padding=18, style="Panel.TFrame")
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
        ttk.Label(self, text="Command Panel", style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            self,
            text="Grouped operator controls for motion, zeroing, and telemetry management.",
            style="PanelSubtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(6, 16))

        absolute = self._create_section("Absolute Move", "Target angle, offset, speed, and direction")
        absolute.grid(row=2, column=0, sticky="ew")
        self._add_labeled_entry(absolute, "Angle (deg)", self._abs_angle, 0)
        self._add_labeled_entry(absolute, "Offset (deg)", self._abs_offset, 1)
        self._add_labeled_entry(absolute, "Speed (deg/s)", self._abs_speed, 2)
        self._add_labeled_combo(absolute, "Direction", self._abs_direction, ("CW", "CCW", "NULL"), 3)
        ttk.Button(absolute, text="Rotate Absolute", style="Primary.TButton", command=self._on_rotate_absolute).grid(
            row=6,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(12, 0),
        )

        constant = self._create_section("Continuous Motion", "Steady rotation until a new command overrides it")
        constant.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        self._add_labeled_entry(constant, "Speed (deg/s)", self._const_speed, 0)
        self._add_labeled_combo(constant, "Direction", self._const_direction, ("CW", "CCW"), 1)
        ttk.Button(constant, text="Constant Rotate", style="Secondary.TButton", command=self._on_constant_rotate).grid(
            row=4,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(12, 0),
        )

        relative = self._create_section("Relative Move", "Incremental correction and alignment control")
        relative.grid(row=4, column=0, sticky="ew", pady=(14, 0))
        self._add_labeled_entry(relative, "Delta (deg)", self._rel_delta, 0)
        self._add_labeled_entry(relative, "Speed (deg/s)", self._rel_speed, 1)
        ttk.Button(relative, text="Rotate Relative", style="Secondary.TButton", command=self._on_rotate_relative).grid(
            row=4,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(12, 0),
        )

        service = self._create_section("Reference and Telemetry", "Zeroing and reporting controls")
        service.grid(row=5, column=0, sticky="ew", pady=(14, 0))
        self._add_labeled_entry(service, "Virtual Zero Offset (deg)", self._vzero_offset, 0)
        self._add_labeled_entry(service, "Telemetry Rate (Hz)", self._telemetry_rate, 1)
        ttk.Button(service, text="Rotate Virtual Zero", style="Secondary.TButton", command=self._on_rotate_virtual_zero).grid(
            row=4,
            column=0,
            sticky="ew",
            pady=(12, 0),
            padx=(0, 6),
        )
        ttk.Button(service, text="Set Telemetry Rate", style="Secondary.TButton", command=self._on_set_telemetry_rate).grid(
            row=4,
            column=1,
            sticky="ew",
            pady=(12, 0),
            padx=(6, 0),
        )
        ttk.Button(service, text="Mechanical Zero", style="Primary.TButton", command=self._on_rotate_mechanical_zero).grid(
            row=5,
            column=0,
            sticky="ew",
            pady=(12, 0),
            padx=(0, 6),
        )
        ttk.Button(service, text="Stop", style="Danger.TButton", command=self._on_stop).grid(
            row=5,
            column=1,
            sticky="ew",
            pady=(12, 0),
            padx=(6, 0),
        )

        self.columnconfigure(0, weight=1)

    def _create_section(self, title: str, subtitle: str) -> ttk.Frame:
        section = ttk.Frame(self, padding=16, style="Card.TFrame")
        section.columnconfigure(1, weight=1)
        ttk.Label(section, text=title, style="SectionTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(section, text=subtitle, style="FieldLabel.TLabel").grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(4, 8),
        )
        return section

    def _add_labeled_entry(self, parent: ttk.Frame, label: str, variable: tk.StringVar, row: int) -> None:
        content_row = row + 2
        ttk.Label(parent, text=label, style="FieldLabel.TLabel").grid(row=content_row, column=0, sticky="w", pady=6)
        ttk.Entry(parent, textvariable=variable).grid(row=content_row, column=1, sticky="ew", pady=6)

    def _add_labeled_combo(
        self,
        parent: ttk.Frame,
        label: str,
        variable: tk.StringVar,
        values: tuple[str, ...],
        row: int,
    ) -> None:
        content_row = row + 2
        ttk.Label(parent, text=label, style="FieldLabel.TLabel").grid(row=content_row, column=0, sticky="w", pady=6)
        ttk.Combobox(parent, textvariable=variable, values=values, state="readonly").grid(
            row=content_row,
            column=1,
            sticky="ew",
            pady=6,
        )

    def _run_action(self, action: Callable[[], object]) -> None:
        try:
            self._status_callback("Command In Progress", "Sending command to the controller preview.", "warning")
            ack = action()
        except Exception as exc:
            self._status_callback("Command Failed", str(exc), "error")
            return
        command_name = getattr(ack, "command_type", "UNKNOWN")
        self._status_callback("Command Accepted", f"ACK received for {command_name}.", "success")

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
