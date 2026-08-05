"""A single sequential job queue for the whole app.

Everything the app does — download a video, grab a playlist, convert 30 files,
pull a Spotify playlist — is a job. One worker thread runs them one at a time,
which is what you want when the work is CPU- and bandwidth-bound anyway, and it
means "Cancel" has exactly one meaning: kill what's running now.
"""

import itertools
import queue
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional

from .proc import Cancelled, Runner

PENDING, RUNNING, DONE, FAILED, CANCELLED, SKIPPED = (
    "pending", "running", "done", "failed", "cancelled", "skipped")

_ids = itertools.count(1)


@dataclass
class Job:
    label: str                       # what the user sees in the queue list
    kind: str                        # "download" | "music" | "edit"
    run: Callable                    # run(job, runner) -> str | None (result note)
    id: int = field(default_factory=lambda: next(_ids))
    status: str = PENDING
    detail: str = ""                 # progress text, then the outcome
    progress: float = 0.0            # 0..1
    result: Optional[str] = None     # output path, shown when done

    @property
    def finished(self):
        return self.status in (DONE, FAILED, CANCELLED, SKIPPED)


class JobQueue:
    """Owns the worker thread and the one Runner that cancellation targets."""

    def __init__(self, log):
        self._log = log
        self._q = queue.Queue()
        # The worker never touches Tk. It bumps this counter instead, and the UI
        # polls it on a Tk timer. Calling into Tkinter from a worker thread can
        # block that thread inside Tcl, which silently stalled the whole queue
        # after the first job.
        self.revision = 0
        self.jobs = []                   # every job ever added, in order
        self.current = None
        self.runner = Runner(log)
        self._lock = threading.Lock()
        self._worker = None
        self._stop_all = False

    # ── Public API ────────────────────────────────────────────────────────────

    def add(self, job):
        with self._lock:
            self.jobs.append(job)
        self._q.put(job)
        self._ensure_worker()
        self._changed()
        return job

    def add_many(self, jobs):
        for j in jobs:
            self.add(j)

    @property
    def pending_count(self):
        return sum(1 for j in self.jobs if j.status == PENDING)

    @property
    def busy(self):
        return self.current is not None or self.pending_count > 0

    def cancel_current(self):
        """Stop the running job; the queue carries on with the next one."""
        self.runner.cancel()

    def cancel_all(self):
        """Stop everything and drop whatever hasn't started."""
        self._stop_all = True
        with self._lock:
            for j in self.jobs:
                if j.status == PENDING:
                    j.status = CANCELLED
                    j.detail = "cancelled before it started"
        self.runner.cancel()
        self._changed()

    def clear_finished(self):
        with self._lock:
            self.jobs = [j for j in self.jobs if not j.finished]
        self._changed()

    # ── Progress helpers, called from inside a job ────────────────────────────

    def set_progress(self, job, value, detail=None):
        job.progress = max(0.0, min(1.0, value))
        if detail is not None:
            job.detail = detail
        self._changed()

    def set_detail(self, job, detail):
        job.detail = detail
        self._changed()

    # ── Worker ────────────────────────────────────────────────────────────────

    def _ensure_worker(self):
        if self._worker is None or not self._worker.is_alive():
            self._stop_all = False
            self._worker = threading.Thread(target=self._loop, daemon=True)
            self._worker.start()

    def _changed(self):
        self.revision += 1

    def _loop(self):
        while True:
            try:
                job = self._q.get(timeout=0.5)
            except queue.Empty:
                if self.pending_count == 0:
                    self.current = None
                    self._changed()
                    return
                continue

            if job.status == CANCELLED:      # cancelled while queued
                continue

            self.current = job
            job.status = RUNNING
            job.detail = "starting…"
            self.runner.reset()
            self._changed()

            try:
                note = job.run(job, self.runner)
                if self.runner.cancelled:
                    job.status = CANCELLED
                    job.detail = "cancelled"
                else:
                    job.status = DONE
                    job.progress = 1.0
                    job.result = note or job.result
                    job.detail = "done"
            except Cancelled:
                job.status = CANCELLED
                job.detail = "cancelled"
            except Exception as e:
                job.status = FAILED
                job.detail = str(e) or e.__class__.__name__
                self._log(f"!  {job.label}: {job.detail}")

            self.current = None
            self._changed()

            if self._stop_all:
                return
