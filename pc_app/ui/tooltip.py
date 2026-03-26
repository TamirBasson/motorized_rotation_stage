from __future__ import annotations

import tkinter as tk


def add_tooltip(widget: tk.Misc, text: str) -> None:
    """Show `text` in a small floating window while the pointer hovers over `widget`."""

    tip: tk.Toplevel | None = None

    def show(event: object) -> None:
        nonlocal tip
        if tip is not None:
            return
        tip = tk.Toplevel(widget)
        tip.wm_overrideredirect(True)
        tip.wmattributes("-topmost", True)
        x = widget.winfo_rootx() + 20
        y = widget.winfo_rooty() + widget.winfo_height() + 4
        tip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tip,
            text=text,
            justify="left",
            background="#1f2830",
            foreground="#e8edf5",
            relief="solid",
            borderwidth=1,
            font=("Segoe UI", 9),
            padx=8,
            pady=6,
            wraplength=360,
        )
        label.pack()

    def hide(event: object) -> None:
        nonlocal tip
        if tip is not None:
            tip.destroy()
            tip = None

    widget.bind("<Enter>", show)
    widget.bind("<Leave>", hide)
