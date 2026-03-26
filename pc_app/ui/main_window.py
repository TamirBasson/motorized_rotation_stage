from __future__ import annotations

from pathlib import Path
import threading
import tkinter as tk
from tkinter import ttk

from pc_app.comm.models import TelemetryState
from pc_app.ui.control_panel import ControlPanel
from pc_app.ui.controller_interface import StageController
from pc_app.ui.system_parameters_panel import SystemParametersPanel
from pc_app.ui.telemetry_view import TelemetryView
from pc_app.ui.theme import apply_dark_theme


class MainWindow(tk.Tk):
    CONTROLLER_TELEMETRY_RATE_HZ = 20
    UI_REFRESH_RATE_HZ = 5
    REFRESH_INTERVAL_MS = int(1000 / UI_REFRESH_RATE_HZ)
    ICON_PATH = Path(__file__).resolve().parents[2] / "assets" / "SvE6bWoR_400x400.png"

    def __init__(self, controller: StageController) -> None:
        super().__init__()
        apply_dark_theme(self)
        self.title("Motorized Rotation Stage")
        self.geometry("1320x860")
        self.minsize(1180, 740)

        self._controller = controller
        self._status_title = tk.StringVar(value="System Ready")
        self._status_message = tk.StringVar(value="Communication manager is active. Use the command panel to control the stage.")
        self._status_tone = tk.StringVar(value="success")
        self._header_icon: tk.PhotoImage | None = self._load_header_icon()
        self._ui_telemetry_lock = threading.Lock()
        self._latest_ui_telemetry: TelemetryState | None = None
        self._telemetry_subscription = None

        container = ttk.Frame(self, padding=16, style="App.TFrame")
        container.pack(fill="both", expand=True)

        self._build_header(container)
        self._build_content(container)
        self._telemetry_subscription = self._controller.subscribe_telemetry(
            self._handle_ui_telemetry,
            replay_latest=True,
            priority="low",
        )

        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)

        if not self._initialize_virtual_zero_on_startup():
            return

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

        title_row = ttk.Frame(header, style="App.TFrame")
        title_row.grid(row=0, column=0, sticky="w")
        if self._header_icon is not None:
            ttk.Label(title_row, image=self._header_icon, style="AppSubtitle.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 14))
        ttk.Label(title_row, text="Motorized Rotation Stage", style="AppTitle.TLabel").grid(row=0, column=1, sticky="w")

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
            "Mechanical Degree is the physical angle of the stage.\n\n"
            "Virtual Degree is defined relative to a user-defined virtual zero reference.\n\n"
            "Mechanical Degree = Virtual Degree + Virtual Zero Reference\n\n"
            "Therefore:\n"
            "Virtual Degree = Mechanical Degree − Virtual Zero Reference"
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
            self._controller.set_telemetry_rate(self.CONTROLLER_TELEMETRY_RATE_HZ)
        except Exception as exc:
            self.set_status("Telemetry Configuration Failed", str(exc), "error")
        else:
            self.set_status(
                "System Ready",
                (
                    f"Controller telemetry is fixed at {self.CONTROLLER_TELEMETRY_RATE_HZ} Hz. "
                    f"UI display refresh is throttled to {self.UI_REFRESH_RATE_HZ} Hz so API consumers stay prioritized."
                ),
                "success",
            )

    def _load_header_icon(self) -> tk.PhotoImage | None:
        try:
            icon = tk.PhotoImage(file=str(self.ICON_PATH))
        except tk.TclError:
            return None
        return icon.subsample(5, 5)

    def _refresh_telemetry(self) -> None:
        with self._ui_telemetry_lock:
            telemetry = self._latest_ui_telemetry
        self._telemetry_view.update_telemetry(telemetry)
        self.after(self.REFRESH_INTERVAL_MS, self._refresh_telemetry)

    def _handle_ui_telemetry(self, telemetry: TelemetryState) -> None:
        with self._ui_telemetry_lock:
            self._latest_ui_telemetry = telemetry

    def shutdown(self) -> None:
        if self._telemetry_subscription is not None:
            self._telemetry_subscription.unsubscribe()
            self._telemetry_subscription = None

    def _initialize_virtual_zero_on_startup(self) -> bool:
        """Block normal operation until virtual zero reference is defined."""
        dialog = tk.Toplevel(self)
        dialog.title("Initialize Virtual Zero")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        value_var = tk.StringVar(value=f"{self._params_panel.get_virtual_zero_offset():.2f}")
        confirmed = tk.BooleanVar(value=False)
        cancelled = tk.BooleanVar(value=False)

        frame = ttk.Frame(dialog, padding=14, style="Panel.TFrame")
        frame.grid(row=0, column=0, sticky="nsew")
        ttk.Label(frame, text="Set Virtual Zero Reference", style="SectionTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            frame,
            text=(
                "Before operating the stage, define the Virtual Zero Reference (deg).\n"
                "This synchronizes the Mechanical and Virtual angle frames."
            ),
            style="PanelSubtitle.TLabel",
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 8))
        ttk.Label(frame, text="Virtual Zero Reference (deg)", style="FieldLabel.TLabel").grid(row=2, column=0, sticky="w")
        entry = ttk.Entry(frame, textvariable=value_var)
        entry.grid(row=2, column=1, sticky="ew", padx=(8, 0))

        message_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=message_var, style="Warning.TLabel").grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))

        def on_confirm() -> None:
            try:
                value_deg = float(value_var.get())
                self._params_panel.set_virtual_zero_offset(value_deg)
                self._controller.rotate_virtual_zero(value_deg)
            except Exception as exc:
                message_var.set(f"Invalid or rejected value: {exc}")
                return
            confirmed.set(True)
            dialog.destroy()

        def on_cancel() -> None:
            cancelled.set(True)
            dialog.destroy()
            self.destroy()

        button_row = ttk.Frame(frame, style="App.TFrame")
        button_row.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        button_row.columnconfigure((0, 1), weight=1)
        ttk.Button(button_row, text="Cancel", style="Secondary.TButton", command=on_cancel).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(button_row, text="Apply and Continue", style="Primary.TButton", command=on_confirm).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        frame.columnconfigure(1, weight=1)
        entry.focus_set()
        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        self.wait_window(dialog)
        return bool(confirmed.get()) and not bool(cancelled.get())
