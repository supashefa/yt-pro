"""First-run setup — downloads the tools the app can't work without.

Deliberately modal and un-closable: without yt-dlp and ffmpeg there is nothing
the app can do, so letting someone dismiss this would only produce a broken
window and a confused user.
"""

import threading

import customtkinter as ctk

from .. import tools
from .theme import MUTED, SUBTLE_BTN, bold, small


class SetupWindow(ctk.CTkToplevel):
    def __init__(self, parent, needed, on_done, title="First Time Setup"):
        super().__init__(parent)
        self.title(f"YT-Pro — {title}")
        self.geometry("470x250")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self.transient(parent)
        self.grab_set()
        self._needed = list(needed)
        self._on_done = on_done
        self._build()
        self.after(300, lambda: threading.Thread(
            target=self._run, daemon=True).start())

    def _build(self):
        ctk.CTkLabel(self, text="Setting up YT-Pro", font=bold(17)).pack(pady=(26, 4))
        sizes = ", ".join(f"{n} ({tools.SIZES.get(n, '')})" for n in self._needed)
        ctk.CTkLabel(self, text=f"Downloading {sizes} — this happens once.",
                     font=small(12), text_color=MUTED, wraplength=420).pack()
        self._lbl = ctk.CTkLabel(self, text="Starting…", font=small(12))
        self._lbl.pack(pady=(18, 4))
        self._bar = ctk.CTkProgressBar(self, width=390, height=8, corner_radius=4)
        self._bar.set(0)
        self._bar.pack()
        self._sub = ctk.CTkLabel(self, text="", font=small(11), text_color=MUTED)
        self._sub.pack(pady=(6, 0))

    def _set(self, label, pct, sub=""):
        def _do():
            if not self.winfo_exists():
                return
            self._lbl.configure(text=label)
            self._bar.set(pct)
            self._sub.configure(text=sub)
        try:
            self.after(0, _do)
        except Exception:
            pass

    def _run(self):
        try:
            steps = max(1, len(self._needed))
            for i, name in enumerate(self._needed):
                base, span = i / steps, 1 / steps
                installer = tools.INSTALLERS.get(name)
                if installer is None:
                    continue

                def hook(done, total, base=base, span=span, name=name):
                    if total:
                        self._set(f"Downloading {name}…",
                                  base + (done / total) * span,
                                  f"{done / 1_048_576:.1f} / {total / 1_048_576:.1f} MB")
                    else:
                        self._set(f"Downloading {name}…", base,
                                  f"{done / 1_048_576:.1f} MB")

                self._set(f"Downloading {name}…", base)
                installer(hook)
                self._set(f"{name}  ✓", base + span)

            self.after(0, self._finish)
        except Exception as e:
            msg = str(e)
            self.after(0, lambda: (
                self._lbl.configure(text="Download failed", text_color="red"),
                self._sub.configure(text=msg[:70]),
                self.protocol("WM_DELETE_WINDOW", self.destroy),
                self._allow_close(),
            ))

    def _allow_close(self):
        ctk.CTkButton(self, text="Close", width=90, command=self.destroy,
                      **SUBTLE_BTN).pack(pady=(10, 0))

    def _finish(self):
        try:
            self._on_done()
        finally:
            self.destroy()
