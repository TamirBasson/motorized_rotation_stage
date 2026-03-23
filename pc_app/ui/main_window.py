from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk

from pc_app.ui.control_panel import ControlPanel
from pc_app.ui.controller_interface import StageController
from pc_app.ui.system_parameters_panel import SystemParametersPanel
from pc_app.ui.telemetry_view import TelemetryView
from pc_app.ui.theme import apply_dark_theme


class MainWindow(tk.Tk):
    TELEMETRY_RATE_HZ = 5
    REFRESH_INTERVAL_MS = int(1000 / TELEMETRY_RATE_HZ)
    ICON_PATH = Path(__file__).resolve().parents[2] / "assets" / "SvE6bWoR_400x400.png"

    def __init__(self, controller: StageController) -> None:
        super().__init__()
        apply_dark_theme(self)
        self.title("Motorized Rotation Stage Controller")
        self.geometry("1320x820")
        self.minsize(1180, 700)

        self._controller = controller
        self._status_title = tk.StringVar(value="System Ready")
        self._status_message = tk.StringVar(value="Communication manager is active. Use the command panel to control the stage.")
        self._status_tone = tk.StringVar(value="success")
        self._connection_state = tk.StringVar(value="Controller Online")
        self._motion_state = tk.StringVar(value="Motor Idle")
        self._queue_state = tk.StringVar(value="No Pending Command")
        self._header_icon: tk.PhotoImage | None = self._load_header_icon()

        container = ttk.Frame(self, padding=16, style="App.TFrame")
        container.pack(fill="both", expand=True)

        self._build_header(container)
        self._build_content(container)

        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)

        self._configure_fixed_telemetry_rate()
        self.after(self.REFRESH_INTERVAL_MS, self._refresh_telemetry)

    def set_status(self, title: str, message: str, tone: str = "success") -> None:
        self._status_title.set(title)
        self._status_message.set(message)
        self._status_tone.set(tone)
        self._apply_status_tone()

    def _build_header(self, container: ttk.Frame) -> None:
        header = ttk.Frame(container, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)
        header.columnconfigure(1, weight=0)

        text_block = ttk.Frame(header, style="App.TFrame")
        text_block.grid(row=0, column=0, sticky="w")

        title_row = ttk.Frame(text_block, style="App.TFrame")
        title_row.grid(row=0, column=0, sticky="w")
        if self._header_icon is not None:
            ttk.Label(title_row, image=self._header_icon, style="AppSubtitle.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 14))
        ttk.Label(title_row, text="Motion Control Dashboard", style="AppTitle.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Label(
            text_block,
            text="Motorized Rotation Stage Controller with live telemetry and grouped operator controls.",
            style="AppSubtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))

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
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.columnconfigure(0, weight=1)

        right = ttk.Frame(content, style="App.TFrame")
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self._telemetry_view = TelemetryView(left)
        self._telemetry_view.grid(row=0, column=0, sticky="new")

        bottom_row = ttk.Frame(left, style="App.TFrame")
        bottom_row.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        bottom_row.columnconfigure(0, weight=1)
        bottom_row.columnconfigure(1, weight=1)

        info = ttk.Frame(bottom_row, padding=10, style="Panel.TFrame")
        info.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        info.columnconfigure(0, weight=1)
        ttk.Label(info, text="Mechanical vs Virtual Degree", style="SectionTitle.TLabel").grid(
            row=0,
            column=0,
            sticky="w",
        )
        explanation = (
            "Mechanical Degree is the true physical angle "
            "of the stage, derived from step count, "
            "steps-per-revolution, and gear ratio. "
            "It resets only via the hardware "
            "mechanical-zero sensor.\n\n"
            "Virtual Degree = Mechanical + Offset.\n"
            "The offset is a user-defined constant that "
            "shifts the reference frame without moving "
            "the stage. Use it to align the display with "
            "your experiment coordinate system."
        )
        ttk.Label(
            info,
            text=explanation,
            style="PanelSubtitle.TLabel",
            wraplength=320,
            justify="left",
        ).grid(row=1, column=0, sticky="nw", pady=(6, 0))

        self._params_panel = SystemParametersPanel(bottom_row)
        self._params_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        self._build_status_bar(left)

        self._control_panel = ControlPanel(
            right,
            controller=self._controller,
            status_callback=self.set_status,
            virtual_zero_offset_provider=self._params_panel.get_virtual_zero_offset,
        )
        self._control_panel.grid(row=0, column=0, sticky="nsew")

    def _build_status_bar(self, parent: ttk.Frame) -> None:
        self._status_frame = ttk.Frame(parent, padding=10, style="Status.TFrame")
        self._status_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self._status_frame.columnconfigure(1, weight=1)
        self._status_indicator = ttk.Label(self._status_frame, text="READY", style="Success.TLabel")
        self._status_indicator.grid(row=0, column=0, sticky="w", padx=(0, 10))
        ttk.Label(self._status_frame, textvariable=self._status_title, style="StatusTitle.TLabel").grid(
            row=0,
            column=1,
            sticky="w",
        )
        ttk.Label(
            self._status_frame,
            textvariable=self._status_message,
            style="StatusMessage.TLabel",
            wraplength=900,
            justify="left",
        ).grid(row=1, column=1, sticky="w", pady=(2, 0))
        self._apply_status_tone()

    def _apply_status_tone(self) -> None:
        tone = self._status_tone.get()
        if tone == "error":
            self._status_indicator.configure(text="ERROR", style="Error.TLabel")
        elif tone == "warning":
            self._status_indicator.configure(text="BUSY", style="Warning.TLabel")
        else:
            self._status_indicator.configure(text="READY", style="Success.TLabel")

    def _configure_fixed_telemetry_rate(self) -> None:
        try:
            self._controller.set_telemetry_rate(self.TELEMETRY_RATE_HZ)
        except Exception as exc:
            self.set_status("Telemetry Configuration Failed", str(exc), "error")
        else:
            self.set_status(
                "System Ready",
                f"Telemetry is fixed at {self.TELEMETRY_RATE_HZ} Hz and managed automatically.",
                "success",
            )

    def _load_header_icon(self) -> tk.PhotoImage | None:
        try:
            icon = tk.PhotoImage(file=str(self.ICON_PATH))
        except tk.TclError:
            return None
        return icon.subsample(5, 5)

    def _refresh_telemetry(self) -> None:
        telemetry = self._controller.get_latest_telemetry()
        self._telemetry_view.update_telemetry(telemetry)
        if telemetry is not None:
            self._motion_state.set("Motor Running" if telemetry.running else "Motor Idle")
            self._queue_state.set("Command Active" if telemetry.running else "No Pending Command")
        self.after(self.REFRESH_INTERVAL_MS, self._refresh_telemetry)
