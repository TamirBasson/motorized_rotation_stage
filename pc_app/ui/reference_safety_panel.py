from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from pc_app.comm.remote_client import CommandQueuedError
from pc_app.ui.controller_interface import StageController


StatusCallback = Callable[[str, str, str], None]


class ReferenceSafetyPanel(ttk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        controller: StageController,
        status_callback: StatusCallback,
    ) -> None:
        super().__init__(master, padding=10, style="Panel.TFrame")
        self._controller = controller
        self._status_callback = status_callback
        self._vzero_offset = tk.StringVar(value="-12.5")
        self._build()

    def _build(self) -> None:
        ttk.Label(self, text="Reference and Safety", style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(self, text="Virtual Zero Reference (deg)", style="FieldLabel.TLabel").grid(
            row=1,
            column=0,
            sticky="w",
            pady=(6, 3),
        )
        ttk.Entry(self, textvariable=self._vzero_offset).grid(row=2, column=0, sticky="ew")

        action_row = ttk.Frame(self, style="Panel.TFrame")
        action_row.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        action_row.columnconfigure((0, 1), weight=1)

        ttk.Button(
            action_row,
            text="Move To Virtual Zero",
            style="Primary.TButton",
            command=self._on_rotate_virtual_zero,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(
            action_row,
            text="Rotate To Mechanical Zero",
            style="Secondary.TButton",
            command=self._on_rotate_mechanical_zero,
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        ttk.Button(self, text="Stop", style="Danger.TButton", command=self._on_stop).grid(
            row=4,
            column=0,
            sticky="ew",
            pady=(8, 0),
        )

        self.columnconfigure(0, weight=1)

    def get_virtual_zero_offset(self) -> float:
        return float(self._vzero_offset.get())

    def _run_action(self, action: Callable[[], object]) -> None:
        try:
            self._status_callback("Command In Progress", "Sending command to the controller preview.", "warning")
            ack = action()
        except CommandQueuedError as exc:
            self._status_callback(
                "Command Queued",
                f"{exc} Queue position: {exc.queue_position}.",
                "warning",
            )
            return
        except Exception as exc:
            self._status_callback("Command Failed", str(exc), "error")
            return
        command_name = getattr(ack, "command_type", "UNKNOWN")
        self._status_callback("Command Accepted", f"ACK received for {command_name}.", "success")

    def _on_rotate_virtual_zero(self) -> None:
        self._run_action(
            lambda: self._controller.rotate_virtual_zero(
                virt_zero_offset_deg=self.get_virtual_zero_offset(),
            )
        )

    def _on_rotate_mechanical_zero(self) -> None:
        self._run_action(self._controller.rotate_mechanical_zero)

    def _on_stop(self) -> None:
        self._run_action(self._controller.stop_rotation)
