"""The shared queue panel that sits under every tab.

Batch work is only useful if you can see it, so this shows one row per job with
its own progress bar and status. It rebuilds only when the job list itself
changes; on a plain progress tick it just updates the existing rows, otherwise
a 200-track playlist would rebuild 200 widgets several times a second.
"""

import os

import customtkinter as ctk

from ..jobs import DONE, FAILED, RUNNING
from .theme import CARD, MUTED, STATUS_COLORS, SUBTLE_BTN, bold, small


class QueuePanel(ctk.CTkFrame):
    def __init__(self, parent, jq, on_view_log):
        super().__init__(parent, **CARD)
        self._jq = jq
        self._rows = {}          # job id -> dict of widgets
        self._on_view_log = on_view_log
        self._seen_revision = -1

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(10, 4))
        self._title = ctk.CTkLabel(head, text="Queue", font=bold(12))
        self._title.pack(side="left")
        self._summary = ctk.CTkLabel(head, text="nothing queued",
                                     font=small(11), text_color=MUTED)
        self._summary.pack(side="left", padx=(10, 0))

        ctk.CTkButton(head, text="Clear finished", width=110, height=26,
                      font=small(11), command=jq.clear_finished,
                      **SUBTLE_BTN).pack(side="right")
        ctk.CTkButton(head, text="View log", width=85, height=26,
                      font=small(11), command=on_view_log,
                      **SUBTLE_BTN).pack(side="right", padx=(0, 6))
        self._stop_btn = ctk.CTkButton(
            head, text="Stop all", width=80, height=26, font=small(11),
            fg_color="gray35", hover_color="#b71c1c", state="disabled",
            command=jq.cancel_all)
        self._stop_btn.pack(side="right", padx=(0, 6))
        self._skip_btn = ctk.CTkButton(
            head, text="Skip", width=60, height=26, font=small(11),
            state="disabled", command=jq.cancel_current, **SUBTLE_BTN)
        self._skip_btn.pack(side="right", padx=(0, 6))

        self._list = ctk.CTkScrollableFrame(self, height=150,
                                            fg_color="transparent")
        self._list.pack(fill="both", expand=True, padx=8, pady=(0, 10))
        self._empty = ctk.CTkLabel(
            self._list,
            text="Queued work shows up here. Nothing running.",
            font=small(11), text_color=MUTED)
        self._empty.pack(pady=18)

    # ── Refresh ───────────────────────────────────────────────────────────────

    def poll(self):
        """Called from the app's Tk timer. Redraws only when the queue actually
        changed, so a 200-track playlist doesn't rebuild widgets on every tick."""
        rev = self._jq.revision
        if rev == self._seen_revision:
            return
        self._seen_revision = rev
        self._refresh()

    def _refresh(self):
        if not self.winfo_exists():
            return
        jobs = list(self._jq.jobs)

        # Drop rows for jobs that no longer exist (Clear finished).
        for jid in [j for j in self._rows if j not in {x.id for x in jobs}]:
            self._rows.pop(jid)["frame"].destroy()

        if jobs:
            self._empty.pack_forget()
        else:
            self._empty.pack(pady=18)

        for job in jobs:
            row = self._rows.get(job.id)
            if row is None:
                row = self._make_row(job)
                self._rows[job.id] = row
            self._update_row(row, job)

        running = sum(1 for j in jobs if j.status == RUNNING)
        pending = self._jq.pending_count
        done = sum(1 for j in jobs if j.status == DONE)
        failed = sum(1 for j in jobs if j.status == FAILED)
        bits = []
        if running:
            bits.append("1 running")
        if pending:
            bits.append(f"{pending} waiting")
        if done:
            bits.append(f"{done} done")
        if failed:
            bits.append(f"{failed} failed")
        self._summary.configure(text="  ·  ".join(bits) or "nothing queued")

        busy = bool(running or pending)
        self._stop_btn.configure(state="normal" if busy else "disabled")
        self._skip_btn.configure(state="normal" if running else "disabled")

    def _make_row(self, job):
        f = ctk.CTkFrame(self._list, fg_color=("gray88", "gray20"),
                         corner_radius=8)
        f.pack(fill="x", pady=3, padx=2)

        top = ctk.CTkFrame(f, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(7, 0))
        label = ctk.CTkLabel(top, text=job.label, font=small(11), anchor="w",
                             justify="left")
        label.pack(side="left", fill="x", expand=True)
        status = ctk.CTkLabel(top, text=job.status, font=small(11))
        status.pack(side="right")

        bar = ctk.CTkProgressBar(f, height=4, corner_radius=2)
        bar.set(0)
        bar.pack(fill="x", padx=10, pady=(4, 2))

        detail = ctk.CTkLabel(f, text="", font=small(10), text_color=MUTED,
                              anchor="w", justify="left")
        detail.pack(fill="x", padx=10, pady=(0, 4))

        open_btn = ctk.CTkButton(f, text="Open folder", width=90, height=22,
                                 font=small(10), **SUBTLE_BTN)
        return {"frame": f, "label": label, "status": status, "bar": bar,
                "detail": detail, "open": open_btn, "open_shown": False}

    def _update_row(self, row, job):
        row["status"].configure(text=job.status,
                                text_color=STATUS_COLORS.get(job.status, MUTED))
        row["bar"].set(1.0 if job.status == DONE else job.progress)
        row["detail"].configure(text=job.detail or "")

        # Only finished-and-successful jobs get an Open folder shortcut.
        want_open = job.status == DONE and job.result
        if want_open and not row["open_shown"]:
            folder = job.result.splitlines()[0]
            folder = folder if os.path.isdir(folder) else os.path.dirname(folder)
            row["open"].configure(
                command=lambda f=folder: os.path.isdir(f) and os.startfile(f))
            row["open"].pack(anchor="w", padx=10, pady=(0, 7))
            row["open_shown"] = True
        elif not want_open and row["open_shown"]:
            row["open"].pack_forget()
            row["open_shown"] = False
