"""The log window — hidden until something goes wrong and you click "View log".

The window never receives text directly from a worker thread. Workers append to
a plain deque (App.log) and the Tk side drains it on a timer. Calling Tkinter
from a worker thread is the kind of bug that shows up as "the queue mysteriously
stopped after one job", so all of it is kept on one side of the fence.
"""

import os
import webbrowser
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .. import report
from .theme import GO_BTN, SUBTLE_BTN


class LogWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.app = parent
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
        ctk.CTkButton(bar, text="Save to file…", width=120, command=self._save,
                      **SUBTLE_BTN).pack(side="left", padx=(0, 8))
        ctk.CTkButton(bar, text="Close", width=90, command=self.withdraw,
                      **SUBTLE_BTN).pack(side="left")
        ctk.CTkButton(bar, text="Report a problem", width=150,
                      command=self._report, **GO_BTN).pack(side="right")
        self.withdraw()

    # ── Reporting ─────────────────────────────────────────────────────────────
    #
    # Everything here is user-initiated and visible. The app never sends a
    # report by itself: the text is put on the clipboard and a prefilled issue
    # is opened in the browser, so whoever clicks it can read what they're
    # about to post and back out.

    def _lines(self):
        return list(getattr(self.app, "_log_lines", []))

    def _text(self):
        return report.build_report(self.app.cfg, self._lines())

    def _save(self):
        path = filedialog.asksaveasfilename(
            parent=self, title="Save problem report",
            initialfile=report.default_filename(),
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self._text())
        except OSError as e:
            messagebox.showerror("Could not save", str(e), parent=self)
            return
        if messagebox.askyesno(
                "Saved",
                f"Report saved to:\n{path}\n\nShow it in the folder?",
                parent=self):
            try:
                os.startfile(os.path.dirname(path))
            except OSError:
                pass

    def _report(self):
        text = self._text()
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            copied = True
        except Exception:
            copied = False
        if not messagebox.askyesno(
                "Report a problem",
                ("The full report is on your clipboard.\n\n" if copied else "")
                + "This opens a new issue on GitHub with your version, which "
                  "tools are installed and the end of the log filled in. Your "
                  "user folder is replaced with %USERPROFILE% first.\n\n"
                  "Nothing is sent until you press Submit there. Open it now?",
                parent=self):
            return
        try:
            webbrowser.open(report.issue_url(self.app.cfg, self._lines()))
        except Exception as e:
            messagebox.showerror(
                "Could not open the browser",
                f"{e}\n\nThe report is on your clipboard — paste it into an "
                f"email instead.", parent=self)

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
