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
        virtual_zero_offset_provider: Callable[[], float],
    ) -> None:
        super().__init__(master, padding=10, style="Panel.TFrame")
        self._controller = controller
        self._status_callback = status_callback
        self._virtual_zero_offset_provider = virtual_zero_offset_provider

        self._abs_angle = tk.StringVar(value="120.0")
        self._abs_speed = tk.StringVar(value="5.0")
        self._abs_direction = tk.StringVar(value="CW")

        self._const_speed = tk.StringVar(value="2.5")
        self._const_direction = tk.StringVar(value="CCW")

        self._rel_delta = tk.StringVar(value="45.0")
        self._rel_speed = tk.StringVar(value="3.0")
        self._rel_direction = tk.StringVar(value="CCW")

        self._build()

    def _build(self) -> None:
        ttk.Label(self, text="Command Panel", style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w")

        absolute = self._create_section(self, "Absolute Move")
        absolute.grid(row=1, column=0, sticky="ew", pady=(3, 0))
        self._add_labeled_entry(absolute, "Angle (deg)", self._abs_angle, 0)
        self._add_labeled_entry(absolute, "Speed (deg/s)", self._abs_speed, 1)
        self._add_labeled_combo(absolute, "Direction", self._abs_direction, ("CW", "CCW"), 2)
        ttk.Button(absolute, text="Rotate Absolute", style="Primary.TButton", command=self._on_rotate_absolute).grid(
            row=4,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(3, 0),
        )

        relative = self._create_section(self, "Delta Move")
        relative.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        self._add_labeled_entry(relative, "Delta (deg, 0-360)", self._rel_delta, 0)
        self._add_labeled_entry(relative, "Speed (deg/s)", self._rel_speed, 1)
        self._add_labeled_combo(relative, "Direction", self._rel_direction, ("CW", "CCW"), 2)
        ttk.Button(relative, text="Move By Delta", style="Secondary.TButton", command=self._on_rotate_relative).grid(
            row=4,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(3, 0),
        )

        constant = self._create_section(self, "Continuous Motion")
        constant.grid(row=3, column=0, sticky="ew", pady=(4, 0))
        self._add_labeled_entry(constant, "Speed (deg/s)", self._const_speed, 0)
        self._add_labeled_combo(constant, "Direction", self._const_direction, ("CW", "CCW"), 1)
        ttk.Button(constant, text="Constant Rotate", style="Secondary.TButton", command=self._on_constant_rotate).grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(3, 0),
        )

        actions = ttk.Frame(self, style="App.TFrame")
        actions.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        actions.columnconfigure((0, 1), weight=1)

        ttk.Button(
            actions, text="Rotate To Virtual Zero", style="Primary.TButton",
            command=self._on_rotate_virtual_zero,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(
            actions, text="Rotate To Mechanical Zero", style="Primary.TButton",
            command=self._on_rotate_mechanical_zero,
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0))
        ttk.Button(
            actions, text="Stop", style="Danger.TButton",
            command=self._on_stop,
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(3, 0))

        self.columnconfigure(0, weight=1)

    def _create_section(self, parent: ttk.Frame, title: str) -> ttk.Frame:
        section = ttk.Frame(parent, padding=6, style="Card.TFrame")
        section.columnconfigure(1, weight=1)
        ttk.Label(section, text=title, style="SectionTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 1))
        return section

    def _add_labeled_entry(self, parent: ttk.Frame, label: str, variable: tk.StringVar, row: int) -> None:
        content_row = row + 1
        ttk.Label(parent, text=label, style="FieldLabel.TLabel").grid(row=content_row, column=0, sticky="w", pady=1)
        ttk.Entry(parent, textvariable=variable).grid(row=content_row, column=1, sticky="ew", pady=1)

    def _add_labeled_combo(
        self,
        parent: ttk.Frame,
        label: str,
        variable: tk.StringVar,
        values: tuple[str, ...],
        row: int,
    ) -> None:
        content_row = row + 1
        ttk.Label(parent, text=label, style="FieldLabel.TLabel").grid(row=content_row, column=0, sticky="w", pady=1)
        ttk.Combobox(parent, textvariable=variable, values=values, state="readonly").grid(
            row=content_row,
            column=1,
            sticky="ew",
            pady=1,
        )

    def _run_action(self, action: Callable[[], object]) -> None:
        try:
            self._status_callback("Command In Progress", "Sending command to the controller.", "warning")
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
                virt_zero_offset_deg=self._virtual_zero_offset_provider(),
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
            self._build_relative_action()
        )

    def _build_relative_action(self) -> Callable[[], object]:
        def action() -> object:
            delta_magnitude_deg = float(self._rel_delta.get())
            if not 0.0 <= delta_magnitude_deg <= 360.0:
                raise ValueError("Delta angle must be within 0 to 360 degrees")
            return self._controller.rotate_relative(
                delta_angle_deg=delta_magnitude_deg,
                speed_deg_per_sec=float(self._rel_speed.get()),
                direction=self._rel_direction.get(),
            )

        return action

    def _on_rotate_virtual_zero(self) -> None:
        self._run_action(
            lambda: self._controller.rotate_virtual_zero(
                virt_zero_offset_deg=self._virtual_zero_offset_provider(),
            )
        )

    def _on_rotate_mechanical_zero(self) -> None:
        self._run_action(self._controller.rotate_mechanical_zero)

    def _on_stop(self) -> None:
        self._run_action(self._controller.stop_rotation)
