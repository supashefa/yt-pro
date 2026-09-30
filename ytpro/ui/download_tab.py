"""Download tab — one or many links, video or audio, whole playlists."""

import os

import customtkinter as ctk
from tkinter import messagebox

from .. import download, formats
from .theme import CARD, GO_BTN, MUTED, SUBTLE_BTN, bold, small

_PLACEHOLDER = ("Paste one or more links — one per line.\n"
                "YouTube · Vimeo · X · TikTok · Instagram · Facebook · Twitch · "
                "Reddit · SoundCloud · and 1000+ more.")


class DownloadTab:
    def __init__(self, parent, app):
        self.app = app
        self._build(parent)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self, p):
        c = ctk.CTkFrame(p, **CARD)
        c.pack(fill="x", padx=8, pady=(10, 6))
        head = ctk.CTkFrame(c, fg_color="transparent")
        head.pack(fill="x", padx=14, pady=(12, 4))
        ctk.CTkLabel(head, text="Links", font=bold(12)).pack(side="left")
        ctk.CTkLabel(head, text="  one per line — the whole list gets queued",
                     font=small(11), text_color=MUTED).pack(side="left")
        ctk.CTkButton(head, text="Paste", width=70, height=26, font=small(11),
                      command=self._paste, **SUBTLE_BTN).pack(side="right")
        ctk.CTkButton(head, text="Clear", width=60, height=26, font=small(11),
                      command=lambda: self.urls.delete("1.0", "end"),
                      **SUBTLE_BTN).pack(side="right", padx=(0, 6))

        self.urls = ctk.CTkTextbox(c, height=76, font=small(12), wrap="none")
        self.urls.pack(fill="x", padx=14, pady=(0, 12))

        # ── Options ──
        c2 = ctk.CTkFrame(p, **CARD)
        c2.pack(fill="x", padx=8, pady=6)

        r1 = ctk.CTkFrame(c2, fg_color="transparent")
        r1.pack(fill="x", padx=14, pady=(12, 8))
        ctk.CTkLabel(r1, text="Type", font=bold(12), width=64,
                     anchor="w").pack(side="left")
        self.mode = ctk.StringVar(value="Video")
        ctk.CTkSegmentedButton(r1, values=["Video", "Audio Only", "Clip"],
                               variable=self.mode,
                               command=self._on_mode).pack(side="left")

        r2 = ctk.CTkFrame(c2, fg_color="transparent")
        r2.pack(fill="x", padx=14, pady=(0, 4))
        ctk.CTkLabel(r2, text="Quality", font=bold(12), width=64,
                     anchor="w").pack(side="left")
        self.quality = ctk.StringVar(value="1080p")
        self.quality_menu = ctk.CTkOptionMenu(
            r2, variable=self.quality, width=112,
            values=formats.DOWNLOAD_QUALITIES, command=lambda _: self._warn())
        self.quality_menu.pack(side="left", padx=(0, 18))
        ctk.CTkLabel(r2, text="Format", font=bold(12)).pack(side="left", padx=(0, 8))
        self.container = ctk.StringVar(value="MP4")
        self.format_menu = ctk.CTkOptionMenu(
            r2, variable=self.container, width=96,
            values=formats.VIDEO_CONTAINERS, command=lambda _: self._warn())
        self.format_menu.pack(side="left")

        # Honest warning instead of a silent downgrade — above 1080p there is no
        # H.264, so an MP4 request gets VP9/AV1 in an MP4 shell.
        self.warn_lbl = ctk.CTkLabel(c2, text="", font=small(11),
                                     text_color=("#e65100", "#ffb74d"),
                                     anchor="w", justify="left")
        self.warn_lbl.pack(fill="x", padx=14, pady=(0, 4))

        self.clip_row = ctk.CTkFrame(c2, fg_color="transparent")
        ctk.CTkLabel(self.clip_row, text="From", font=bold(12), width=64,
                     anchor="w").pack(side="left")
        self.clip_start = ctk.CTkEntry(self.clip_row, placeholder_text="00:00:00",
                                       width=105, height=34)
        self.clip_start.pack(side="left", padx=(0, 16))
        ctk.CTkLabel(self.clip_row, text="To", font=bold(12)).pack(
            side="left", padx=(0, 8))
        self.clip_end = ctk.CTkEntry(self.clip_row, placeholder_text="00:00:00",
                                     width=105, height=34)
        self.clip_end.pack(side="left")

        r4 = ctk.CTkFrame(c2, fg_color="transparent")
        r4.pack(fill="x", padx=14, pady=(0, 12))
        self.playlist = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(r4, text="Whole playlist / channel if the link is one",
                        variable=self.playlist, font=small(11)).pack(side="left")
        self.redownload = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(r4, text="Re-download if it already exists",
                        variable=self.redownload, font=small(11)).pack(
            side="left", padx=(16, 0))

        # ── Save to ──
        c3 = ctk.CTkFrame(p, **CARD)
        c3.pack(fill="x", padx=8, pady=6)
        r5 = ctk.CTkFrame(c3, fg_color="transparent")
        r5.pack(fill="x", padx=14, pady=10)
        ctk.CTkLabel(r5, text="Save to", font=bold(12), width=64,
                     anchor="w").pack(side="left")
        self.out_dir = ctk.StringVar(value=self.app.cfg["download_dir"])
        ctk.CTkEntry(r5, textvariable=self.out_dir, height=34).pack(
            side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(r5, text="Browse", width=80, height=34,
                      command=lambda: self.app.pick_dir(self.out_dir)).pack(side="left")

        btn = ctk.CTkFrame(p, fg_color="transparent")
        btn.pack(fill="x", padx=8, pady=(12, 4))
        ctk.CTkButton(btn, text="Add to queue", height=46, font=bold(16),
                      command=self._enqueue, **GO_BTN).pack(fill="x")

        self._on_mode("Video")

    # ── Behaviour ─────────────────────────────────────────────────────────────

    def _on_mode(self, val):
        if val == "Audio Only":
            self.clip_row.pack_forget()
            self.quality_menu.configure(state="disabled")
            self.format_menu.configure(values=formats.AUDIO_CONTAINERS)
            self.container.set("MP3")
        else:
            self.quality_menu.configure(state="normal")
            self.format_menu.configure(values=formats.VIDEO_CONTAINERS)
            if self.container.get() not in formats.VIDEO_CONTAINERS:
                self.container.set("MP4")
            if val == "Clip":
                self.clip_row.pack(fill="x", padx=14, pady=(0, 8))
            else:
                self.clip_row.pack_forget()
        self._warn()

    def _warn(self):
        q, fmt = self.quality.get(), self.container.get()
        msg = ""
        if self.mode.get() != "Audio Only" and fmt == "MP4" and q.endswith("p"):
            try:
                if int(q[:-1]) > formats.H264_CEILING:
                    msg = (f"Above {formats.H264_CEILING}p there is no H.264 — "
                           f"your MP4 will hold a VP9 or AV1 track. Most players "
                           f"handle it; pick MKV if yours doesn't.")
            except ValueError:
                pass
        self.warn_lbl.configure(text=msg)

    def _paste(self):
        try:
            text = self.app.clipboard_get().strip()
        except Exception:
            return
        if text:
            current = self.urls.get("1.0", "end").strip()
            self.urls.insert("end", ("\n" if current else "") + text)

    def _links(self):
        raw = self.urls.get("1.0", "end")
        seen, out = set(), []
        for line in raw.splitlines():
            u = line.strip()
            # Tolerate pasted numbered lists and stray quotes.
            u = u.strip('"\'' ).strip()
            if not u or u.startswith("#") or u in seen:
                continue
            if not (u.startswith("http://") or u.startswith("https://")):
                continue
            seen.add(u)
            out.append(u)
        return out

    def _enqueue(self):
        links = self._links()
        if not links:
            messagebox.showwarning(
                "No links", "Paste at least one http(s) link — one per line.")
            return
        ytdlp = self.app.cfg.get("ytdlp", "")
        if not ytdlp or not os.path.exists(ytdlp):
            messagebox.showerror("Setup needed",
                                 "yt-dlp wasn't found. Check the Settings tab.")
            return
        out_dir = self.out_dir.get().strip()
        if not out_dir:
            messagebox.showwarning("No folder", "Choose a folder to save into.")
            return
        if not self.app.ensure_dir(out_dir):
            return

        mode = self.mode.get()
        for url in links:
            as_playlist = self.playlist.get() and download.looks_like_playlist(url)
            label = f"{mode} — {_short(url)}" + (" (playlist)" if as_playlist else "")
            self.app.jq.add(download.make_job(
                queue=self.app.jq, label=label, out_dir=out_dir,
                ytdlp=ytdlp, ffmpeg=self.app.cfg.get("ffmpeg", ""),
                url=url, mode=mode, quality=self.quality.get(),
                container=self.container.get(),
                clip_start=self.clip_start.get(), clip_end=self.clip_end.get(),
                playlist=as_playlist, redownload=self.redownload.get()))

        self.urls.delete("1.0", "end")


def _short(url, n=52):
    u = url.split("://", 1)[-1]
    return u if len(u) <= n else u[:n - 1] + "…"
