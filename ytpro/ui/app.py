"""The main window — owns the config, the job queue, and the four tabs.

Threading rule for the whole app, in one place: **worker threads never touch
Tk.** Jobs mutate plain Python state (job status, a log deque, a revision
counter) and the UI polls that state on a Tk timer. Calling Tkinter from a
worker can block the worker inside Tcl, which presents as the queue quietly
dying after one job — so there is exactly one thread allowed to draw.
"""

import sys
import threading
from collections import deque

import customtkinter as ctk
from tkinter import filedialog, messagebox

from .. import __version__, tools
from ..config import load_config, save_config
from ..jobs import JobQueue
from .download_tab import DownloadTab
from .edit_tab import EditTab
from .logwin import LogWindow
from .music_tab import MusicTab
from .queue_panel import QueuePanel
from .settings_tab import SettingsTab
from .theme import MUTED, apply_theme, bold, small

TICK_MS = 150          # how often the UI picks up worker-thread state
LOG_CAP = 20_000       # lines kept in memory


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        apply_theme()
        self.title(f"YT-Pro {__version__}")
        self.geometry("760x780")
        self.minsize(660, 620)

        # Note: NOT self.config — that's tkinter's own widget method, and
        # shadowing it (as the old single-file version did) is a landmine.
        self.cfg = load_config()
        tools.autodetect(self.cfg)

        # Log lines live here, written by any thread, drained by the Tk tick.
        self._log_lines = deque(maxlen=LOG_CAP)
        self._log_shown = 0
        self._log_win = None

        self.jq = JobQueue(self.log)

        self._build()
        self._tick()
        self.after(150, self._first_run)

    # ── Logging ───────────────────────────────────────────────────────────────

    def log(self, text):
        """Safe from any thread — a deque append and nothing else."""
        for line in str(text).splitlines() or [""]:
            self._log_lines.append(line)

    def show_log(self):
        if self._log_win is None or not self._log_win.winfo_exists():
            self._log_win = LogWindow(self)
            self._log_win.replace(list(self._log_lines))
            self._log_shown = len(self._log_lines)
        self._log_win.show()

    def _drain_log(self):
        win = self._log_win
        if win is None or not win.winfo_exists():
            # Nothing is displaying yet; lines stay buffered until it opens.
            self._log_shown = len(self._log_lines)
            return
        total = len(self._log_lines)
        if total < self._log_shown:
            self._log_shown = 0      # deque rolled over
        if total > self._log_shown:
            new = list(self._log_lines)[self._log_shown:]
            win.write(new)
            self._log_shown = total

    # ── The one UI timer ──────────────────────────────────────────────────────

    def _tick(self):
        try:
            self._drain_log()
            self.queue_panel.poll()
        except Exception:
            pass
        finally:
            self.after(TICK_MS, self._tick)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=22, pady=(16, 2))
        ctk.CTkLabel(hdr, text="YT-Pro", font=bold(24)).pack(side="left")
        ctk.CTkLabel(hdr, text="  Media Toolkit", font=small(13),
                     text_color=MUTED).pack(side="left", pady=(5, 0))

        self.tabs = ctk.CTkTabview(self, anchor="nw")
        self.tabs.pack(padx=15, pady=(4, 6), fill="both", expand=True)
        for name in ("Download", "Music", "Edit", "Settings"):
            self.tabs.add(name)

        self.download_tab = DownloadTab(self.tabs.tab("Download"), self)
        self.music_tab = MusicTab(self.tabs.tab("Music"), self)
        self.edit_tab = EditTab(self.tabs.tab("Edit"), self)
        self.settings_tab = SettingsTab(self.tabs.tab("Settings"), self)

        # The queue lives outside the tabs on purpose: work you started on one
        # tab stays visible while you set up work on another.
        self.queue_panel = QueuePanel(self, self.jq, self.show_log)
        self.queue_panel.pack(fill="x", padx=15, pady=(0, 14))

    # ── First run ─────────────────────────────────────────────────────────────

    def _first_run(self):
        missing = tools.missing_core(self.cfg)
        if missing:
            self.install_tools(missing, on_done=self._after_setup)
        else:
            self._background_checks()

    def _after_setup(self):
        tools.autodetect(self.cfg, force=True)
        self.refresh_settings()
        # Freshly installed, so there's nothing to update yet.
        tools.mark_updated()

    def install_tools(self, names, on_done=None):
        from .setup import SetupWindow

        def done():
            tools.autodetect(self.cfg, force=True)
            self.refresh_settings()
            if on_done:
                on_done()

        SetupWindow(self, names, done)

    def _background_checks(self):
        """Runs off-thread; anything that needs a dialog is handed back to the
        Tk thread through _pending_update rather than calling Tk directly."""
        self._pending_update = None

        def work():
            try:
                tools.update_tools(self.cfg, self.jq.runner, self.log)
            except Exception as e:
                self.log(f"Tool update check failed: {e}")
            if self.cfg.get("check_app_updates", True):
                try:
                    self._pending_update = tools.check_app_update(self.log)
                except Exception:
                    self._pending_update = None

        threading.Thread(target=work, daemon=True).start()
        self.after(4000, self._consume_pending_update)

    def _consume_pending_update(self):
        found = getattr(self, "_pending_update", None)
        if found:
            self._pending_update = None
            self.offer_app_update(*found)

    # ── App self-update ───────────────────────────────────────────────────────

    def offer_app_update(self, tag, url, sha256=""):
        if not getattr(sys, "frozen", False):
            self.log(f"YT-Pro {tag} is out — you're running from source, "
                     f"so pull instead of self-updating.")
            return
        if not messagebox.askyesno(
                "Update available",
                f"YT-Pro {tag} is available (you have {__version__}).\n\n"
                f"Download it and restart now?"):
            return
        self.log(f"Downloading YT-Pro {tag}…")
        self.show_log()
        self._update_error = None

        def work():
            try:
                tools.apply_app_update(url, expected_sha256=sha256)
                self._update_ready = True
            except Exception as e:
                self._update_error = str(e)
                self.log(f"Update failed: {self._update_error}")

        self._update_ready = False
        threading.Thread(target=work, daemon=True).start()
        self.after(1000, self._poll_update)

    def _poll_update(self):
        if getattr(self, "_update_error", None):
            err, self._update_error = self._update_error, None
            messagebox.showerror("Update failed",
                                 f"Could not install the update:\n{err}")
            return
        if getattr(self, "_update_ready", False):
            messagebox.showinfo(
                "Restarting",
                "YT-Pro will close and reopen on the new version.")
            self.destroy()
            return
        self.after(1000, self._poll_update)

    # ── Shared helpers used by the tabs ───────────────────────────────────────

    def pick_dir(self, var):
        d = filedialog.askdirectory(initialdir=var.get() or None)
        if d:
            var.set(d)

    def refresh_settings(self):
        try:
            self.settings_tab.refresh()
        except Exception:
            pass

    def on_config_saved(self):
        """Settings were saved — push the folder choices into the other tabs."""
        self.download_tab.out_dir.set(self.cfg.get("download_dir", ""))
        self.edit_tab.out_dir.set(self.cfg.get("download_dir", ""))
        self.music_tab.out_dir.set(self.cfg.get("music_dir", ""))

    # ── Closing ───────────────────────────────────────────────────────────────

    def destroy(self):
        # Remember the folders the user actually ended up using.
        try:
            self.cfg["download_dir"] = self.download_tab.out_dir.get()
            self.cfg["music_dir"] = self.music_tab.out_dir.get()
            save_config(self.cfg)
        except Exception:
            pass
        try:
            self.jq.cancel_all()
        except Exception:
            pass
        super().destroy()


def main():
    app = App()

    def on_close():
        if app.jq.busy and not messagebox.askyesno(
                "Still working", "There's work in the queue. Quit anyway?"):
            return
        app.destroy()

    app.protocol("WM_DELETE_WINDOW", on_close)
    app.mainloop()
