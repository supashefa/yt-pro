"""Edit tab — ffmpeg operations, on one file or on a whole batch.

Two changes from the old version worth knowing about:

- The file picker takes **multiple** files, and each one becomes its own queued
  job. Converting thirty clips is now one click.
- The output format list includes AVI, MOV, FLV, FLAC, OPUS and OGG, plus a
  "Same as input" default. Those were missing before, which is why "convert to
  AVI" simply wasn't possible.
"""

import os
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, messagebox

from .. import edit, formats
from .theme import CARD, GO_BTN, MUTED, SUBTLE_BTN, bold, small

_ALL_CONTAINERS = ([formats.SAME_AS_INPUT] + formats.VIDEO_CONTAINERS +
                   formats.AUDIO_CONTAINERS)


class EditTab:
    def __init__(self, parent, app):
        self.app = app
        self.files = []
        self._opt_widgets = {}
        self._build(parent)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self, p):
        c = ctk.CTkFrame(p, **CARD)
        c.pack(fill="x", padx=8, pady=(10, 6))
        head = ctk.CTkFrame(c, fg_color="transparent")
        head.pack(fill="x", padx=14, pady=(12, 4))
        ctk.CTkLabel(head, text="Input files", font=bold(12)).pack(side="left")
        self.count_lbl = ctk.CTkLabel(head, text="  nothing chosen",
                                      font=small(11), text_color=MUTED)
        self.count_lbl.pack(side="left")
        ctk.CTkButton(head, text="Add files…", width=100, height=26,
                      font=small(11), command=self._add_files,
                      **SUBTLE_BTN).pack(side="right")
        ctk.CTkButton(head, text="Clear", width=60, height=26, font=small(11),
                      command=self._clear_files,
                      **SUBTLE_BTN).pack(side="right", padx=(0, 6))

        self.file_list = ctk.CTkTextbox(c, height=68, font=small(11),
                                        wrap="none", state="disabled")
        self.file_list.pack(fill="x", padx=14, pady=(0, 4))
        ctk.CTkLabel(c, text="Any format ffmpeg can read — AVI, WMV, MOV, FLV, "
                            "MPEG, TS and the rest all work.",
                     font=small(10), text_color=MUTED, anchor="w").pack(
            fill="x", padx=14, pady=(0, 10))

        # ── Operation ──
        c2 = ctk.CTkFrame(p, **CARD)
        c2.pack(fill="x", padx=8, pady=6)
        ctk.CTkLabel(c2, text="What do you want to do?", font=bold(12)).pack(
            anchor="w", padx=14, pady=(12, 8))

        r1 = ctk.CTkFrame(c2, fg_color="transparent")
        r1.pack(fill="x", padx=14, pady=(0, 8))
        self.op = ctk.StringVar(value="Trim")
        ctk.CTkOptionMenu(r1, variable=self.op, width=190,
                          values=edit.OPERATIONS,
                          command=self._refresh_opts).pack(side="left", padx=(0, 18))
        ctk.CTkLabel(r1, text="Output format", font=small(12)).pack(
            side="left", padx=(0, 8))
        self.fmt = ctk.StringVar(value=formats.SAME_AS_INPUT)
        ctk.CTkOptionMenu(r1, variable=self.fmt, width=140,
                          values=_ALL_CONTAINERS).pack(side="left")

        self.opts = ctk.CTkFrame(c2, fg_color="transparent")
        self.opts.pack(fill="x", padx=14, pady=(0, 12))

        # ── Save to ──
        c3 = ctk.CTkFrame(p, **CARD)
        c3.pack(fill="x", padx=8, pady=6)
        r3 = ctk.CTkFrame(c3, fg_color="transparent")
        r3.pack(fill="x", padx=14, pady=10)
        ctk.CTkLabel(r3, text="Save to", font=bold(12), width=64,
                     anchor="w").pack(side="left")
        self.out_dir = ctk.StringVar(value=self.app.cfg["download_dir"])
        ctk.CTkEntry(r3, textvariable=self.out_dir, height=34).pack(
            side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(r3, text="Browse", width=80, height=34,
                      command=lambda: self.app.pick_dir(self.out_dir)).pack(side="left")

        btn = ctk.CTkFrame(p, fg_color="transparent")
        btn.pack(fill="x", padx=8, pady=(12, 4))
        ctk.CTkButton(btn, text="Add to queue", height=46, font=bold(16),
                      command=self._enqueue, **GO_BTN).pack(fill="x")

        self._refresh_opts("Trim")

    # ── Per-operation options ─────────────────────────────────────────────────

    def _refresh_opts(self, op):
        for w in self.opts.winfo_children():
            w.destroy()
        self._opt_widgets = {}

        if op == "Trim":
            ctk.CTkLabel(self.opts, text="From", font=bold(12), width=44,
                         anchor="w").pack(side="left", padx=(0, 4))
            e1 = ctk.CTkEntry(self.opts, placeholder_text="00:00:00",
                              width=110, height=34)
            e1.pack(side="left", padx=(0, 16))
            ctk.CTkLabel(self.opts, text="To", font=bold(12)).pack(
                side="left", padx=(0, 8))
            e2 = ctk.CTkEntry(self.opts, placeholder_text="00:00:00 (or blank for the end)",
                              width=200, height=34)
            e2.pack(side="left")
            self._opt_widgets = {"start": e1, "end": e2}

        elif op == "Compress / Resize":
            ctk.CTkLabel(self.opts, text="Height", font=small(12)).pack(
                side="left", padx=(0, 8))
            v = ctk.StringVar(value="720p")
            ctk.CTkOptionMenu(self.opts, variable=v, width=110,
                              values=formats.RESIZE_HEIGHTS).pack(side="left")
            self._opt_widgets = {"height": v}

        elif op == "Combine Files":
            ctk.CTkLabel(self.opts, text="Join on", font=bold(12), width=60,
                         anchor="w").pack(side="left", padx=(0, 4))
            v = ctk.StringVar()
            ctk.CTkEntry(self.opts, textvariable=v, height=34,
                         placeholder_text="Second file…", width=220).pack(
                side="left", padx=(0, 8))
            ctk.CTkButton(self.opts, text="Browse", width=75, height=34,
                          command=lambda: self._pick_second(v)).pack(side="left")
            self._opt_widgets = {"second": v}

        elif op == "Change Speed":
            ctk.CTkLabel(self.opts, text="Speed", font=bold(12), width=50,
                         anchor="w").pack(side="left", padx=(0, 4))
            v = ctk.StringVar(value="1.5")
            ctk.CTkEntry(self.opts, textvariable=v, width=80, height=34).pack(
                side="left", padx=(0, 8))
            ctk.CTkLabel(self.opts, text="×   (0.25 – 4.0)", font=small(11),
                         text_color=MUTED).pack(side="left")
            self._opt_widgets = {"speed": v}

        elif op == "Extract Audio":
            ctk.CTkLabel(self.opts,
                         text="Pick an audio format above — MP3, M4A, WAV, "
                              "FLAC, OPUS or OGG.",
                         font=small(11), text_color=MUTED).pack(side="left")

    def _pick_second(self, var):
        f = filedialog.askopenfilename(filetypes=formats.INPUT_FILETYPES)
        if f:
            var.set(f)

    # ── Files ─────────────────────────────────────────────────────────────────

    def _add_files(self):
        chosen = filedialog.askopenfilenames(filetypes=formats.INPUT_FILETYPES)
        added = False
        for f in chosen:
            if f not in self.files:
                self.files.append(f)
                added = True
        if added and len(self.files) == len(chosen):
            # First batch — default the output folder next to the source, which
            # is almost always what's wanted.
            self.out_dir.set(str(Path(self.files[0]).parent))
        self._render_files()

    def _clear_files(self):
        self.files = []
        self._render_files()

    def _render_files(self):
        self.file_list.configure(state="normal")
        self.file_list.delete("1.0", "end")
        for f in self.files:
            self.file_list.insert("end", Path(f).name + "\n")
        self.file_list.configure(state="disabled")
        n = len(self.files)
        self.count_lbl.configure(
            text="  nothing chosen" if not n else
            f"  {n} file{'s' if n != 1 else ''}")

    # ── Queueing ──────────────────────────────────────────────────────────────

    def _enqueue(self):
        if not self.files:
            messagebox.showwarning("No files", "Add at least one input file.")
            return
        ffmpeg = self.app.cfg.get("ffmpeg", "")
        if not ffmpeg or not os.path.exists(ffmpeg):
            messagebox.showerror("Setup needed",
                                 "ffmpeg wasn't found. Check the Settings tab.")
            return
        out_dir = self.out_dir.get().strip()
        if not out_dir:
            messagebox.showwarning("No folder", "Choose a folder to save into.")
            return

        op = self.op.get()
        if op == "Combine Files" and len(self.files) > 1:
            messagebox.showinfo(
                "One at a time",
                "Combine joins the chosen file to one other file, so it runs on "
                "a single input. Keep one file in the list.")
            return

        chosen_fmt = self.fmt.get()
        if op == "Extract Audio" and chosen_fmt != formats.SAME_AS_INPUT and \
                not formats.is_audio_container(chosen_fmt):
            messagebox.showwarning(
                "Pick an audio format",
                "Extract Audio needs an audio output format — "
                "MP3, M4A, WAV, FLAC, OPUS or OGG.")
            return

        extra = {k: (v.get() if hasattr(v, "get") else v)
                 for k, v in self._opt_widgets.items()}

        for src in self.files:
            ext = formats.resolve_output_ext(chosen_fmt, src)
            if op == "Extract Audio" and not formats.is_audio_container(ext):
                ext = "mp3"
            params = {"input": src, "out_dir": out_dir, "ext": ext, **extra}
            self.app.jq.add(edit.make_job(
                queue=self.app.jq, ffmpeg=ffmpeg, log=self.app.log,
                op=op, params=params))

        self._clear_files()
