"""Music tab — Spotify, Apple Music and YouTube Music links, via spotdl.

The explanatory note in the UI is not padding. "Download from Spotify" is
impossible, and a tool that silently does something else is a tool you can't
trust. Saying plainly that the audio comes from YouTube and the tags come from
Spotify is what makes the results make sense.
"""

import os

import customtkinter as ctk
from tkinter import messagebox

from .. import music, tools
from .setup import SetupWindow
from .theme import CARD, GO_BTN, MUTED, SUBTLE_BTN, bold, small

_EXPLAINER = (
    "Spotify's audio is encrypted and cannot be downloaded. What happens instead: "
    "the link's track list is read, each song is found on YouTube, and the real "
    "title, artist, album, track number and cover art are written onto the file. "
    "You get a properly tagged library."
)

_LOOSE_HINT = (
    "Accepts less exact matches. Finds songs whose spelling differs — "
    "transliterated Hebrew especially — but can return a cover or a live "
    "version instead of the real track."
)


class MusicTab:
    def __init__(self, parent, app):
        self.app = app
        self._installing = False
        self._build(parent)

    def _build(self, p):
        note = ctk.CTkFrame(p, **CARD)
        note.pack(fill="x", padx=8, pady=(10, 6))
        ctk.CTkLabel(note, text="How this works", font=bold(12)).pack(
            anchor="w", padx=14, pady=(10, 2))
        ctk.CTkLabel(note, text=_EXPLAINER, font=small(11), text_color=MUTED,
                     wraplength=600, justify="left", anchor="w").pack(
            fill="x", padx=14, pady=(0, 10))

        c = ctk.CTkFrame(p, **CARD)
        c.pack(fill="x", padx=8, pady=6)
        head = ctk.CTkFrame(c, fg_color="transparent")
        head.pack(fill="x", padx=14, pady=(12, 4))
        ctk.CTkLabel(head, text="Links or search terms", font=bold(12)).pack(side="left")
        ctk.CTkButton(head, text="Paste", width=70, height=26, font=small(11),
                      command=self._paste, **SUBTLE_BTN).pack(side="right")
        self.links = ctk.CTkTextbox(c, height=70, font=small(12), wrap="none")
        self.links.pack(fill="x", padx=14, pady=(0, 4))
        ctk.CTkLabel(c, text=music.SUPPORTED_HINT, font=small(10),
                     text_color=MUTED, anchor="w").pack(fill="x", padx=14, pady=(0, 12))

        c2 = ctk.CTkFrame(p, **CARD)
        c2.pack(fill="x", padx=8, pady=6)
        r1 = ctk.CTkFrame(c2, fg_color="transparent")
        r1.pack(fill="x", padx=14, pady=(12, 8))
        ctk.CTkLabel(r1, text="Format", font=bold(12), width=64,
                     anchor="w").pack(side="left")
        self.fmt = ctk.StringVar(value="MP3")
        ctk.CTkOptionMenu(r1, variable=self.fmt, width=96,
                          values=music.AUDIO_FORMATS).pack(side="left", padx=(0, 18))
        ctk.CTkLabel(r1, text="Bitrate", font=bold(12)).pack(side="left", padx=(0, 8))
        self.bitrate = ctk.StringVar(value="Best available")
        ctk.CTkOptionMenu(r1, variable=self.bitrate, width=130,
                          values=music.BITRATES).pack(side="left")

        r2 = ctk.CTkFrame(c2, fg_color="transparent")
        r2.pack(fill="x", padx=14, pady=(0, 12))
        ctk.CTkLabel(r2, text="Folders", font=bold(12), width=64,
                     anchor="w").pack(side="left")
        self.layout = ctk.StringVar(value=list(music.LAYOUTS)[0])
        ctk.CTkOptionMenu(r2, variable=self.layout, width=210,
                          values=list(music.LAYOUTS)).pack(side="left")

        r4 = ctk.CTkFrame(c2, fg_color="transparent")
        r4.pack(fill="x", padx=14, pady=(0, 12))
        self.loose = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(r4, text="Search harder", variable=self.loose,
                        font=small(12)).pack(side="left", padx=(64, 10))
        ctk.CTkLabel(r4, text=_LOOSE_HINT, font=small(10), text_color=MUTED,
                     wraplength=420, justify="left", anchor="w").pack(
            side="left", fill="x", expand=True)

        c3 = ctk.CTkFrame(p, **CARD)
        c3.pack(fill="x", padx=8, pady=6)
        r3 = ctk.CTkFrame(c3, fg_color="transparent")
        r3.pack(fill="x", padx=14, pady=10)
        ctk.CTkLabel(r3, text="Save to", font=bold(12), width=64,
                     anchor="w").pack(side="left")
        self.out_dir = ctk.StringVar(value=self.app.cfg.get("music_dir", ""))
        ctk.CTkEntry(r3, textvariable=self.out_dir, height=34).pack(
            side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(r3, text="Browse", width=80, height=34,
                      command=lambda: self.app.pick_dir(self.out_dir)).pack(side="left")

        btn = ctk.CTkFrame(p, fg_color="transparent")
        btn.pack(fill="x", padx=8, pady=(12, 4))
        self.go = ctk.CTkButton(btn, text="Add to queue", height=46, font=bold(16),
                                command=self._enqueue, **GO_BTN)
        self.go.pack(fill="x")

    # ── Behaviour ─────────────────────────────────────────────────────────────

    def _paste(self):
        try:
            text = self.app.clipboard_get().strip()
        except Exception:
            return
        if text:
            current = self.links.get("1.0", "end").strip()
            self.links.insert("end", ("\n" if current else "") + text)

    def _items(self):
        seen, out = set(), []
        for line in self.links.get("1.0", "end").splitlines():
            u = line.strip().strip('"\'').strip()
            if u and not u.startswith("#") and u not in seen:
                seen.add(u)
                out.append(u)
        return out

    def _ensure_spotdl(self, then):
        """spotdl is a 46 MB download, so it's fetched the first time this tab is
        actually used rather than during first-run setup. Someone who never
        touches music never pays for it."""
        path = self.app.cfg.get("spotdl", "")
        if path and os.path.exists(path):
            then(path)
            return
        tools.autodetect(self.app.cfg)
        path = self.app.cfg.get("spotdl", "")
        if path and os.path.exists(path):
            then(path)
            return
        if self._installing:
            return
        if not messagebox.askyesno(
                "Get spotdl?",
                "Music support needs spotdl (about 46 MB). Download it now?"):
            return
        self._installing = True

        def done():
            self._installing = False
            tools.autodetect(self.app.cfg, force=True)
            new = self.app.cfg.get("spotdl", "")
            self.app.refresh_settings()
            if new and os.path.exists(new):
                then(new)

        SetupWindow(self.app, ["spotdl"], done, title="Music Support")

    def _enqueue(self):
        items = self._items()
        if not items:
            messagebox.showwarning(
                "Nothing to do", "Paste a Spotify link, or type a song name.")
            return
        out_dir = self.out_dir.get().strip()
        if not out_dir:
            messagebox.showwarning("No folder", "Choose a folder to save into.")
            return
        os.makedirs(out_dir, exist_ok=True)

        def go(spotdl):
            for item in items:
                self.app.jq.add(music.make_job(
                    queue=self.app.jq,
                    label=f"Music — {_short(item)}",
                    out_dir=out_dir, spotdl=spotdl, cfg=self.app.cfg,
                    ffmpeg=self.app.cfg.get("ffmpeg", ""), url=item,
                    audio_format=self.fmt.get(), bitrate=self.bitrate.get(),
                    layout=music.LAYOUTS[self.layout.get()],
                    loose=self.loose.get()))
            self.links.delete("1.0", "end")

        self._ensure_spotdl(go)


def _short(text, n=48):
    t = text.split("://", 1)[-1]
    return t if len(t) <= n else t[:n - 1] + "…"
