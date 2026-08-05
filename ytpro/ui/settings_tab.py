"""Settings tab — tool paths, folders, and the update controls."""

import os
import threading

import customtkinter as ctk
from tkinter import filedialog, messagebox

from .. import GITHUB_REPO, UPDATE_URL, __version__, tools
from ..config import TOOLS_DIR, save_config
from .theme import CARD, MUTED, SUBTLE_BTN, bold, small

_SITES = (
    "Video:  YouTube · Vimeo · X / Twitter · TikTok · Instagram · Facebook · "
    "Twitch · Reddit · Dailymotion · Rumble · Odysee · Bilibili · and 1000+ more\n"
    "Music:  Spotify · Apple Music · YouTube Music · SoundCloud\n\n"
    "Paste any link in the Download or Music tab — the right tool is picked "
    "automatically."
)


class SettingsTab:
    def __init__(self, parent, app):
        self.app = app
        self._build(parent)

    def _build(self, p):
        c = ctk.CTkFrame(p, **CARD)
        c.pack(fill="x", padx=8, pady=(10, 6))
        ctk.CTkLabel(c, text="Tools", font=bold(13)).pack(
            anchor="w", padx=14, pady=(12, 2))
        ctk.CTkLabel(c, text=f"Managed copies live in {TOOLS_DIR}",
                     font=small(10), text_color=MUTED, anchor="w").pack(
            fill="x", padx=14, pady=(0, 8))

        self.vars = {}

        def tool_row(label, key, is_exe=True):
            r = ctk.CTkFrame(c, fg_color="transparent")
            r.pack(fill="x", padx=14, pady=(0, 8))
            ctk.CTkLabel(r, text=label, width=140, anchor="w",
                         font=small(12)).pack(side="left")
            var = ctk.StringVar(value=self.app.cfg.get(key, ""))
            self.vars[key] = var
            ctk.CTkEntry(r, textvariable=var, height=34).pack(
                side="left", fill="x", expand=True, padx=(0, 8))
            cmd = ((lambda v=var: self._browse_exe(v)) if is_exe
                   else (lambda v=var: self.app.pick_dir(v)))
            ctk.CTkButton(r, text="Browse", width=80, height=34,
                          command=cmd).pack(side="left")

        tool_row("yt-dlp.exe", "ytdlp")
        tool_row("ffmpeg.exe", "ffmpeg")
        tool_row("spotdl.exe", "spotdl")
        tool_row("Video folder", "download_dir", is_exe=False)
        tool_row("Music folder", "music_dir", is_exe=False)

        br = ctk.CTkFrame(c, fg_color="transparent")
        br.pack(fill="x", padx=14, pady=(4, 14))
        ctk.CTkButton(br, text="Auto-detect", width=120,
                      command=self._autodetect).pack(side="left", padx=(0, 8))
        ctk.CTkButton(br, text="Save", width=100,
                      command=self._save).pack(side="left", padx=(0, 8))
        ctk.CTkButton(br, text="Install missing", width=130,
                      command=self._install_missing,
                      **SUBTLE_BTN).pack(side="left")

        # ── Updates ──
        c2 = ctk.CTkFrame(p, **CARD)
        c2.pack(fill="x", padx=8, pady=6)
        ctk.CTkLabel(c2, text="Updates", font=bold(13)).pack(
            anchor="w", padx=14, pady=(12, 2))
        ctk.CTkLabel(
            c2,
            text="yt-dlp is checked once a day on launch. This is not optional "
                 "housekeeping — a stale yt-dlp is the reason downloaders stop "
                 "working after a few weeks.",
            font=small(11), text_color=MUTED, wraplength=600,
            justify="left", anchor="w").pack(fill="x", padx=14, pady=(0, 8))

        r = ctk.CTkFrame(c2, fg_color="transparent")
        r.pack(fill="x", padx=14, pady=(0, 8))
        ctk.CTkButton(r, text="Update tools now", width=150,
                      command=self._update_now).pack(side="left", padx=(0, 8))
        ctk.CTkButton(r, text="Check for a new YT-Pro", width=180,
                      command=self._check_app, **SUBTLE_BTN).pack(side="left")

        self.app_updates = ctk.BooleanVar(
            value=bool(self.app.cfg.get("check_app_updates", True)))
        ctk.CTkCheckBox(c2, text="Check for new YT-Pro versions on launch",
                        variable=self.app_updates, font=small(11),
                        command=self._save_flag).pack(
            anchor="w", padx=14, pady=(0, 12))

        # ── Supported sites ──
        c3 = ctk.CTkFrame(p, **CARD)
        c3.pack(fill="both", expand=True, padx=8, pady=6)
        ctk.CTkLabel(c3, text="What works", font=bold(13)).pack(
            anchor="w", padx=14, pady=(12, 6))
        tb = ctk.CTkTextbox(c3, height=105, font=small(11), wrap="word")
        tb.pack(fill="x", padx=14, pady=(0, 8))
        tb.insert("end", _SITES)
        tb.configure(state="disabled")
        ctk.CTkLabel(c3, text=f"YT-Pro {__version__}", font=small(10),
                     text_color=MUTED, anchor="w").pack(
            fill="x", padx=14, pady=(0, 12))

    # ── Actions ───────────────────────────────────────────────────────────────

    def _browse_exe(self, var):
        f = filedialog.askopenfilename(
            filetypes=[("Executables", "*.exe"), ("All files", "*.*")])
        if f:
            var.set(f)

    def refresh(self):
        """Pull the current config back into the entry boxes — used after an
        install or auto-detect changes things behind the UI's back."""
        for key, var in self.vars.items():
            var.set(self.app.cfg.get(key, ""))

    def _autodetect(self):
        tools.autodetect(self.app.cfg, force=True)
        self.refresh()
        found = [k for k in ("ytdlp", "ffmpeg", "spotdl") if self.app.cfg.get(k)]
        if found:
            messagebox.showinfo(
                "Auto-detect",
                "Found: " + ", ".join(found) + ".\n\nAnything still blank can be "
                "installed with \"Install missing\".")
        else:
            messagebox.showwarning(
                "Auto-detect",
                "No tools found on this machine. Use \"Install missing\" to "
                "download them.")

    def _save(self):
        for key, var in self.vars.items():
            self.app.cfg[key] = var.get().strip()
        save_config(self.app.cfg)
        self.app.on_config_saved()
        messagebox.showinfo("Saved", "Settings saved.")

    def _save_flag(self):
        self.app.cfg["check_app_updates"] = bool(self.app_updates.get())
        save_config(self.app.cfg)

    def _install_missing(self):
        want = [name for name, key in
                (("yt-dlp", "ytdlp"), ("ffmpeg", "ffmpeg"), ("spotdl", "spotdl"))
                if not self.app.cfg.get(key) or not os.path.exists(self.app.cfg[key])]
        if not want:
            messagebox.showinfo("Nothing to do", "All three tools are present.")
            return
        self.app.install_tools(want, on_done=self.refresh)

    def _update_now(self):
        def work():
            tools.update_tools(self.app.cfg, self.app.jq.runner, self.app.log,
                               force=True)
            self.app.log("Tool update check finished.")
        self.app.log("Updating tools…")
        self.app.show_log()
        threading.Thread(target=work, daemon=True).start()

    def _check_app(self):
        def work():
            found = tools.check_app_update(self.app.log)
            self._found_update = found
            self.app.after(0, self._report_app_check)

        self._found_update = None
        threading.Thread(target=work, daemon=True).start()

    def _report_app_check(self):
        found, self._found_update = self._found_update, None
        if found:
            self.app.offer_app_update(*found)
        elif not (UPDATE_URL or GITHUB_REPO):
            messagebox.showinfo(
                "Not configured",
                "No update source is set for this build, so there is nothing to "
                "check. UPDATE_URL in ytpro/__init__.py controls this.")
        else:
            messagebox.showinfo(
                "Up to date",
                f"You're on YT-Pro {__version__}, which is the newest version "
                f"available.")
