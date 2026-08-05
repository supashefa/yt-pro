"""The log window — hidden until something goes wrong and you click "View log".

The window never receives text directly from a worker thread. Workers append to
a plain deque (App.log) and the Tk side drains it on a timer. Calling Tkinter
from a worker thread is the kind of bug that shows up as "the queue mysteriously
stopped after one job", so all of it is kept on one side of the fence.
"""

import customtkinter as ctk

from .theme import SUBTLE_BTN


class LogWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Log — YT-Pro")
        self.geometry("820x460")
        self.minsize(520, 260)
        self.protocol("WM_DELETE_WINDOW", self.withdraw)

        self.textbox = ctk.CTkTextbox(
            self, font=ctk.CTkFont(family="Consolas", size=11),
            state="disabled", wrap="none")
        self.textbox.pack(fill="both", expand=True, padx=12, pady=(12, 6))

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=(0, 12))
        ctk.CTkButton(bar, text="Copy all", width=100, command=self._copy,
                      **SUBTLE_BTN).pack(side="left", padx=(0, 8))
        ctk.CTkButton(bar, text="Close", width=90, command=self.withdraw,
                      **SUBTLE_BTN).pack(side="left")
        self.withdraw()

    def show(self):
        self.deiconify()
        self.lift()
        self.focus()

    def write(self, lines):
        """Append already-collected lines. Tk thread only."""
        if not lines:
            return
        self.textbox.configure(state="normal")
        self.textbox.insert("end", "\n".join(lines) + "\n")
        self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def replace(self, lines):
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        if lines:
            self.textbox.insert("end", "\n".join(lines) + "\n")
        self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def _copy(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(self.textbox.get("1.0", "end"))
        except Exception:
            pass
