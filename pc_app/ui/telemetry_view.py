from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from pc_app.comm.models import TelemetryState


class TelemetryView(ttk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=18, style="Panel.TFrame")
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
        ttk.Label(
            self,
            text="Large engineering readouts for fast interpretation under lab conditions.",
            style="PanelSubtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(6, 16))

        hero = ttk.Frame(self, style="Panel.TFrame")
        hero.grid(row=2, column=0, sticky="ew")
        hero.columnconfigure(0, weight=1)
        hero.columnconfigure(1, weight=1)

        self._build_value_card(hero, 0, "Mechanical Angle (deg)", "mechanical_angle_deg", hero_value=True)
        self._build_value_card(hero, 1, "Virtual Angle (deg)", "virtual_angle_deg", hero_value=True)

        metrics = ttk.Frame(self, style="Panel.TFrame")
        metrics.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        metrics.columnconfigure((0, 1), weight=1)

        self._build_metric_card(metrics, 0, 0, "Running", "running")
        self._build_metric_card(metrics, 0, 1, "Speed (deg/s)", "speed_deg_per_sec")
        self._build_metric_card(metrics, 1, 0, "Direction", "direction")
        self._build_metric_card(metrics, 1, 1, "Steps", "steps")

        self.columnconfigure(0, weight=1)

    def _build_value_card(self, parent: ttk.Frame, column: int, label_text: str, key: str, hero_value: bool = False) -> None:
        card = ttk.Frame(parent, padding=18, style="Card.TFrame")
        card.grid(row=0, column=column, sticky="nsew", padx=(0, 8) if column == 0 else (8, 0))
        ttk.Label(card, text=label_text, style="ValueLabel.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            card,
            textvariable=self._values[key],
            style="HeroValue.TLabel" if hero_value else "MetricValue.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(10, 0))

    def _build_metric_card(self, parent: ttk.Frame, row: int, column: int, label_text: str, key: str) -> None:
        card = ttk.Frame(parent, padding=16, style="Card.TFrame")
        card.grid(row=row, column=column, sticky="nsew", padx=6, pady=6)
        ttk.Label(card, text=label_text, style="ValueLabel.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(card, textvariable=self._values[key], style="MetricValue.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))

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
