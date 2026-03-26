from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class SystemParametersPanel(ttk.Frame):
    """System parameters panel with a fixed motor gear ratio."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=10, style="Panel.TFrame")
        self._steps_per_rev = tk.StringVar(value="200")
        self._gear_ratio = tk.StringVar(value="180")
        self._virtual_offset = tk.StringVar(value="-12.5")
        self._build()

    def _build(self) -> None:
        ttk.Label(self, text="System Parameters", style="SectionTitle.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 4),
        )

        ttk.Label(self, text="Steps / Revolution", style="FieldLabel.TLabel").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Entry(self, textvariable=self._steps_per_rev, width=10).grid(row=1, column=1, sticky="ew", pady=2)

        ttk.Label(self, text="Gear Ratio", style="FieldLabel.TLabel").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Entry(self, textvariable=self._gear_ratio, width=10, state="readonly").grid(row=2, column=1, sticky="ew", pady=2)

        ttk.Label(self, text="Virtual Zero Reference (deg)", style="FieldLabel.TLabel").grid(row=3, column=0, sticky="w", pady=2)
        ttk.Entry(self, textvariable=self._virtual_offset, width=10).grid(row=3, column=1, sticky="ew", pady=2)

        self.columnconfigure(1, weight=1)

    def get_steps_per_rev(self) -> int:
        return int(self._steps_per_rev.get())

    def get_gear_ratio(self) -> int:
        return int(self._gear_ratio.get())

    def get_virtual_zero_offset(self) -> float:
        return float(self._virtual_offset.get())
