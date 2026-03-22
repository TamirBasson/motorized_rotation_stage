from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from pc_app.ui.control_panel import ControlPanel
from pc_app.ui.controller_interface import StageController
from pc_app.ui.telemetry_view import TelemetryView


class MainWindow(tk.Tk):
    REFRESH_INTERVAL_MS = 500

    def __init__(self, controller: StageController) -> None:
        super().__init__()
        self.title("Motorized Rotation Stage Controller")
        self.geometry("880x520")

        self._controller = controller
        self._status = tk.StringVar(value="Ready")

        container = ttk.Frame(self, padding=12)
        container.pack(fill="both", expand=True)

        self._control_panel = ControlPanel(container, controller=controller, status_callback=self._status.set)
        self._control_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        self._telemetry_view = TelemetryView(container)
        self._telemetry_view.grid(row=0, column=1, sticky="nsew")

        ttk.Label(container, textvariable=self._status, anchor="w").grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(12, 0),
        )

        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(0, weight=1)

        self.after(self.REFRESH_INTERVAL_MS, self._refresh_telemetry)

    def _refresh_telemetry(self) -> None:
        self._telemetry_view.update_telemetry(self._controller.get_latest_telemetry())
        self.after(self.REFRESH_INTERVAL_MS, self._refresh_telemetry)
