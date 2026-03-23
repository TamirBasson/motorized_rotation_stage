from __future__ import annotations

import tkinter as tk
from tkinter import ttk


COLORS = {
    "bg": "#0b1220",
    "panel": "#121d2d",
    "panel_alt": "#172437",
    "card": "#1b2a40",
    "border": "#23344d",
    "accent": "#5ea2ff",
    "accent_active": "#7ab4ff",
    "danger": "#ff6d7a",
    "warning": "#f3bc63",
    "success": "#58d3a4",
    "text": "#f8fbff",
    "text_soft": "#aab7ca",
    "text_muted": "#7d8da4",
    "input": "#0f1826",
}


def apply_dark_theme(root: tk.Tk) -> ttk.Style:
    style = ttk.Style(root)
    style.theme_use("clam")

    root.configure(bg=COLORS["bg"])

    style.configure(".", background=COLORS["bg"], foreground=COLORS["text"])
    style.configure("App.TFrame", background=COLORS["bg"])
    style.configure("Panel.TFrame", background=COLORS["panel"], relief="flat")
    style.configure("Card.TFrame", background=COLORS["card"], relief="flat")
    style.configure("Status.TFrame", background=COLORS["panel_alt"], relief="flat")

    style.configure(
        "AppTitle.TLabel",
        background=COLORS["bg"],
        foreground=COLORS["text"],
        font=("Segoe UI Semibold", 24),
    )
    style.configure(
        "AppSubtitle.TLabel",
        background=COLORS["bg"],
        foreground=COLORS["text_soft"],
        font=("Segoe UI", 10),
    )
    style.configure(
        "PanelTitle.TLabel",
        background=COLORS["panel"],
        foreground=COLORS["text"],
        font=("Segoe UI Semibold", 13),
    )
    style.configure(
        "PanelSubtitle.TLabel",
        background=COLORS["panel"],
        foreground=COLORS["text_muted"],
        font=("Segoe UI", 8),
    )
    style.configure(
        "SectionTitle.TLabel",
        background=COLORS["card"],
        foreground=COLORS["text"],
        font=("Segoe UI Semibold", 10),
    )
    style.configure(
        "FieldLabel.TLabel",
        background=COLORS["card"],
        foreground=COLORS["text_soft"],
        font=("Segoe UI", 8),
    )
    style.configure(
        "ValueLabel.TLabel",
        background=COLORS["card"],
        foreground=COLORS["text_muted"],
        font=("Segoe UI", 8),
    )
    style.configure(
        "HeroValue.TLabel",
        background=COLORS["card"],
        foreground=COLORS["text"],
        font=("Segoe UI Semibold", 20),
    )
    style.configure(
        "MetricValue.TLabel",
        background=COLORS["card"],
        foreground=COLORS["text"],
        font=("Segoe UI Semibold", 14),
    )
    style.configure(
        "StatusTitle.TLabel",
        background=COLORS["panel_alt"],
        foreground=COLORS["text"],
        font=("Segoe UI Semibold", 11),
    )
    style.configure(
        "StatusMessage.TLabel",
        background=COLORS["panel_alt"],
        foreground=COLORS["text_soft"],
        font=("Segoe UI", 9),
    )
    style.configure(
        "Pill.TLabel",
        background=COLORS["card"],
        foreground=COLORS["text_soft"],
        font=("Segoe UI Semibold", 9),
        padding=(10, 6),
        borderwidth=1,
        relief="solid",
    )
    style.configure(
        "PillAccent.TLabel",
        background=COLORS["card"],
        foreground=COLORS["accent"],
        font=("Segoe UI Semibold", 9),
        padding=(10, 6),
        borderwidth=1,
        relief="solid",
    )
    style.configure(
        "Accent.TLabel",
        background=COLORS["card"],
        foreground=COLORS["accent"],
        font=("Segoe UI Semibold", 14),
    )
    style.configure(
        "Success.TLabel",
        background=COLORS["panel_alt"],
        foreground=COLORS["success"],
        font=("Segoe UI Semibold", 9),
    )
    style.configure(
        "Warning.TLabel",
        background=COLORS["panel_alt"],
        foreground=COLORS["warning"],
        font=("Segoe UI Semibold", 9),
    )
    style.configure(
        "Error.TLabel",
        background=COLORS["panel_alt"],
        foreground=COLORS["danger"],
        font=("Segoe UI Semibold", 9),
    )

    style.configure(
        "TEntry",
        fieldbackground=COLORS["input"],
        background=COLORS["input"],
        foreground=COLORS["text"],
        bordercolor=COLORS["border"],
        lightcolor=COLORS["border"],
        darkcolor=COLORS["border"],
        insertcolor=COLORS["text"],
        padding=6,
    )
    style.map("TEntry", bordercolor=[("focus", COLORS["accent"])])

    style.configure(
        "TCombobox",
        fieldbackground=COLORS["input"],
        background=COLORS["input"],
        foreground=COLORS["text"],
        arrowcolor=COLORS["text"],
        bordercolor=COLORS["border"],
        lightcolor=COLORS["border"],
        darkcolor=COLORS["border"],
        padding=4,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", COLORS["input"])],
        selectbackground=[("readonly", COLORS["input"])],
        selectforeground=[("readonly", COLORS["text"])],
    )

    style.configure(
        "Primary.TButton",
        background=COLORS["accent"],
        foreground=COLORS["text"],
        borderwidth=0,
        focusthickness=0,
        focuscolor=COLORS["accent"],
        padding=(12, 8),
        font=("Segoe UI Semibold", 10),
    )
    style.map(
        "Primary.TButton",
        background=[("active", COLORS["accent_active"]), ("disabled", COLORS["border"])],
        foreground=[("disabled", COLORS["text_muted"])],
    )

    style.configure(
        "Secondary.TButton",
        background=COLORS["card"],
        foreground=COLORS["text"],
        borderwidth=1,
        focusthickness=0,
        focuscolor=COLORS["card"],
        padding=(12, 8),
        font=("Segoe UI Semibold", 10),
    )
    style.map(
        "Secondary.TButton",
        background=[("active", COLORS["panel_alt"]), ("disabled", COLORS["border"])],
        foreground=[("disabled", COLORS["text_muted"])],
    )

    style.configure(
        "Danger.TButton",
        background=COLORS["danger"],
        foreground=COLORS["text"],
        borderwidth=0,
        focusthickness=0,
        focuscolor=COLORS["danger"],
        padding=(12, 8),
        font=("Segoe UI Semibold", 10),
    )
    style.map(
        "Danger.TButton",
        background=[("active", "#ff8892"), ("disabled", COLORS["border"])],
        foreground=[("disabled", COLORS["text_muted"])],
    )

    style.configure("TSeparator", background=COLORS["border"])
    return style
