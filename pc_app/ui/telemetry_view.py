from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from pc_app.comm.models import TelemetryState
from pc_app.ui.tooltip import add_tooltip

# Uniform column group keeps left/right cells equal width when the window resizes.
_GRID_UNIFORM = "telemetry_cols"
# Minimum column width (px) so cards stay stable when labels update.
_COL_MINSIZE = 240
# Character widths for value labels (ttk.Label width is in text units) — prevents IDLE/RUNNING jitter.
_W_HERO = 12
_W_METRIC = 14


class TelemetryView(ttk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=12, style="Panel.TFrame")
        self._values: dict[str, tk.StringVar] = {
            "mechanical_angle_deg": tk.StringVar(value="--"),
            "virtual_angle_deg": tk.StringVar(value="--"),
            "running": tk.StringVar(value="--"),
            "speed_deg_per_sec": tk.StringVar(value="--"),
            "direction": tk.StringVar(value="--"),
            "steps": tk.StringVar(value="--"),
        }
        self._build()

    def _build(self) -> None:
        ttk.Label(self, text="Telemetry Panel", style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w")

        grid = ttk.Frame(self, style="Panel.TFrame")
        grid.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        grid.columnconfigure(0, weight=1, uniform=_GRID_UNIFORM, minsize=_COL_MINSIZE)
        grid.columnconfigure(1, weight=1, uniform=_GRID_UNIFORM, minsize=_COL_MINSIZE)
        for r in range(3):
            grid.rowconfigure(r, weight=0)

        # Three rows × two columns: fixed layout, equal column widths.
        self._build_card(
            grid,
            0,
            0,
            "Mechanical Degree",
            "mechanical_angle_deg",
            hero=True,
            tooltip=(
                "Physical angle of the stage from step count and configuration. "
                "Mechanical = Virtual + Virtual Zero Reference."
            ),
            value_width=_W_HERO,
        )
        self._build_card(
            grid,
            0,
            1,
            "Virtual Degree",
            "virtual_angle_deg",
            hero=True,
            tooltip=(
                "Angle in the user-defined virtual frame. "
                "Virtual = Mechanical − Virtual Zero Reference."
            ),
            value_width=_W_HERO,
        )
        self._build_card(
            grid,
            1,
            0,
            "Running",
            "running",
            hero=False,
            tooltip="Motion state reported by the controller.",
            value_width=8,
        )
        self._build_card(
            grid,
            1,
            1,
            "Speed (deg/s)",
            "speed_deg_per_sec",
            hero=False,
            tooltip="Current commanded/estimated stage speed in degrees per second.",
            value_width=_W_METRIC,
        )
        self._build_card(
            grid,
            2,
            0,
            "Direction",
            "direction",
            hero=False,
            value_width=6,
        )
        self._build_card(
            grid,
            2,
            1,
            "Steps",
            "steps",
            hero=False,
            tooltip="Integrated step position from the controller.",
            value_width=_W_METRIC,
        )

        self.columnconfigure(0, weight=1)

    def _build_card(
        self,
        parent: ttk.Frame,
        row: int,
        column: int,
        label_text: str,
        key: str,
        *,
        hero: bool,
        tooltip: str | None = None,
        value_width: int,
    ) -> None:
        card = ttk.Frame(parent, padding=10, style="Card.TFrame")
        padx = (0, 6) if column == 0 else (6, 0)
        pady = (0, 8) if row < 2 else (0, 0)
        card.grid(row=row, column=column, sticky="nsew", padx=padx, pady=pady)
        card.columnconfigure(0, weight=1)

        title = ttk.Label(card, text=label_text, style="ValueLabel.TLabel")
        title.grid(row=0, column=0, sticky="w")
        if tooltip:
            add_tooltip(title, tooltip)

        value_style = "HeroValue.TLabel" if hero else "MetricValue.TLabel"
        ttk.Label(
            card,
            textvariable=self._values[key],
            style=value_style,
            width=value_width,
            anchor="e",
        ).grid(row=1, column=0, sticky="ew", pady=(6, 0))

    def update_telemetry(self, telemetry: TelemetryState | None) -> None:
        if telemetry is None:
            for value in self._values.values():
                value.set("--")
            return

        self._values["mechanical_angle_deg"].set(f"{telemetry.mechanical_angle_deg:.2f}")
        self._values["virtual_angle_deg"].set(f"{telemetry.virtual_angle_deg:.2f}")
        self._values["running"].set("RUNNING" if telemetry.running else "IDLE")
        self._values["speed_deg_per_sec"].set(f"{telemetry.speed_deg_per_sec:.2f}")
        self._values["direction"].set(telemetry.direction.value)
        self._values["steps"].set(f"{telemetry.steps:,}")
