"""Shared look-and-feel constants, so the tabs stay visually consistent."""

import customtkinter as ctk

CARD = {"corner_radius": 14, "fg_color": ("gray92", "gray16")}
MUTED = ("gray50", "gray55")
OK = ("#2e7d32", "#66bb6a")
BAD = ("red4", "#ef5350")
SUBTLE_BTN = {"fg_color": "gray28", "hover_color": "gray22"}
GO_BTN = {"fg_color": "#2e7d32", "hover_color": "#1b5e20"}
CANCEL_BTN = {"fg_color": "gray35", "hover_color": "#b71c1c"}

STATUS_COLORS = {
    "pending":   MUTED,
    "running":   ("#1565c0", "#64b5f6"),
    "done":      OK,
    "failed":    BAD,
    "cancelled": MUTED,
    "skipped":   MUTED,
}


def apply_theme():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")


def bold(size=12):
    return ctk.CTkFont(size=size, weight="bold")


def small(size=11):
    return ctk.CTkFont(size=size)


def card(parent):
    return ctk.CTkFrame(parent, **CARD)


def card_title(parent, text, pady=(12, 6)):
    return ctk.CTkLabel(parent, text=text, font=bold(12)).pack(
        anchor="w", padx=14, pady=pady)


def row(parent, **kw):
    f = ctk.CTkFrame(parent, fg_color="transparent")
    f.pack(fill="x", **kw)
    return f
