from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from pc_app.ui.control_panel import ControlPanel
from pc_app.ui.controller_interface import StageController
from pc_app.ui.telemetry_view import TelemetryView
from pc_app.ui.theme import apply_dark_theme


class MainWindow(tk.Tk):
    REFRESH_INTERVAL_MS = 500

    def __init__(self, controller: StageController) -> None:
        super().__init__()
        apply_dark_theme(self)
        self.title("Motorized Rotation Stage Controller")
        self.geometry("1320x860")
        self.minsize(1180, 760)

        self._controller = controller
        self._status_title = tk.StringVar(value="System Ready")
        self._status_message = tk.StringVar(value="Preview UI is active. Use the command panel to simulate motion.")
        self._status_tone = tk.StringVar(value="success")
        self._connection_state = tk.StringVar(value="Controller Online")
        self._motion_state = tk.StringVar(value="Motor Idle")
        self._queue_state = tk.StringVar(value="No Pending Command")

        container = ttk.Frame(self, padding=20, style="App.TFrame")
        container.pack(fill="both", expand=True)

        self._build_header(container)
        self._build_content(container)
        self._build_status_bar(container)

        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)

        self.after(self.REFRESH_INTERVAL_MS, self._refresh_telemetry)

    def set_status(self, title: str, message: str, tone: str = "success") -> None:
        self._status_title.set(title)
        self._status_message.set(message)
        self._status_tone.set(tone)
        self._apply_status_tone()

    def _build_header(self, container: ttk.Frame) -> None:
        header = ttk.Frame(container, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        header.columnconfigure(0, weight=1)
        header.columnconfigure(1, weight=0)

        text_block = ttk.Frame(header, style="App.TFrame")
        text_block.grid(row=0, column=0, sticky="w")
        ttk.Label(text_block, text="Lab Motion Dashboard", style="AppTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            text_block,
            text="Motorized Rotation Stage Controller with live telemetry and grouped operator controls.",
            style="AppSubtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

        pill_block = ttk.Frame(header, style="App.TFrame")
        pill_block.grid(row=0, column=1, sticky="e")
        ttk.Label(pill_block, textvariable=self._connection_state, style="PillAccent.TLabel").grid(
            row=0,
            column=0,
            padx=(0, 10),
        )
        ttk.Label(pill_block, textvariable=self._motion_state, style="Pill.TLabel").grid(row=0, column=1, padx=(0, 10))
        ttk.Label(pill_block, textvariable=self._queue_state, style="Pill.TLabel").grid(row=0, column=2)

    def _build_content(self, container: ttk.Frame) -> None:
        content = ttk.Frame(container, style="App.TFrame")
        content.grid(row=1, column=0, sticky="nsew")
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=2)
        content.rowconfigure(0, weight=1)

        left = ttk.Frame(content, style="App.TFrame")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)

        right = ttk.Frame(content, style="App.TFrame")
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self._telemetry_view = TelemetryView(left)
        self._telemetry_view.grid(row=0, column=0, sticky="nsew")

        self._control_panel = ControlPanel(right, controller=self._controller, status_callback=self.set_status)
        self._control_panel.grid(row=0, column=0, sticky="nsew")

    def _build_status_bar(self, container: ttk.Frame) -> None:
        self._status_frame = ttk.Frame(container, padding=16, style="Status.TFrame")
        self._status_frame.grid(row=2, column=0, sticky="ew", pady=(18, 0))
        self._status_frame.columnconfigure(0, weight=1)
        self._status_indicator = ttk.Label(self._status_frame, text="READY", style="Success.TLabel")
        self._status_indicator.grid(row=0, column=0, sticky="w")
        ttk.Label(self._status_frame, textvariable=self._status_title, style="StatusTitle.TLabel").grid(
            row=1,
            column=0,
            sticky="w",
            pady=(4, 0),
        )
        ttk.Label(
            self._status_frame,
            textvariable=self._status_message,
            style="StatusMessage.TLabel",
            wraplength=1080,
            justify="left",
        ).grid(row=2, column=0, sticky="w", pady=(6, 0))
        self._apply_status_tone()

    def _apply_status_tone(self) -> None:
        tone = self._status_tone.get()
        if tone == "error":
            self._status_indicator.configure(text="ERROR", style="Error.TLabel")
        elif tone == "warning":
            self._status_indicator.configure(text="BUSY", style="Warning.TLabel")
        else:
            self._status_indicator.configure(text="READY", style="Success.TLabel")

    def _refresh_telemetry(self) -> None:
        telemetry = self._controller.get_latest_telemetry()
        self._telemetry_view.update_telemetry(telemetry)
        if telemetry is not None:
            self._motion_state.set("Motor Running" if telemetry.running else "Motor Idle")
            self._queue_state.set("Command Active" if telemetry.running else "No Pending Command")
        self.after(self.REFRESH_INTERVAL_MS, self._refresh_telemetry)
