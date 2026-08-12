"""Subprocess plumbing — one place that knows how to run a console tool without
flashing a black window, stream its output to the log, and be cancelled."""

import os
import re
import subprocess

# Popen flag that suppresses the console window. Windows-only; zero elsewhere so
# the module still imports if someone runs this on another OS.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def child_env():
    """Environment for every tool we launch, asking for UTF-8 output.

    We read their output as UTF-8, but a child writing to a pipe encodes with
    the system code page — cp1252 on most Windows installs — so a Hebrew name
    can raise UnicodeEncodeError inside the tool itself.

    Worth knowing what this does and doesn't buy: the PyInstaller builds we
    download ignore both of these (measured — spotdl.exe crashed identically
    with and without them), so the real defence for spotdl is --simple-tui in
    music.build_command. These still help anyone pointing the app at a
    pip-installed spotdl or yt-dlp, where they work as advertised, and they
    cost nothing.
    """
    from .config import TOOLS_DIR  # here, to keep this module import-light

    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    # Our tools folder goes on PATH so yt-dlp finds the Deno we installed for
    # it. Prepended, not appended: if a JavaScript runtime is going to be
    # picked, it should be the one we know the version of.
    env["PATH"] = str(TOOLS_DIR) + os.pathsep + env.get("PATH", "")
    return env


def quote(cmd):
    return " ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd)


class Cancelled(Exception):
    """Raised so a job stops without being reported as a failure."""


class Runner:
    """Runs one command at a time and remembers it, so cancel() can kill it.

    A single Runner is owned by the job queue worker, which means "Cancel"
    always targets whatever is actually running right now.
    """

    def __init__(self, log):
        self._log = log
        self._proc = None
        self.cancelled = False

    def log(self, message):
        """Write a line to the same log the running tool's output goes to, so a
        job can explain what it's doing between commands."""
        self._log(message)

    # ── Streaming run — used for anything with progress output ────────────────

    def run(self, cmd, on_line=None, tidy=None):
        """Run cmd, streaming stdout+stderr line by line. Returns the exit code
        (-1 if the executable could not be started).

        `tidy`, if given, sees every raw line first and returns what should be
        logged instead — or None to drop it. Both the log and `on_line` see the
        tidied version, so a job can rescue readable text out of a tool that
        spews, without the progress parser and the log window disagreeing about
        what happened.
        """
        if self.cancelled:
            raise Cancelled()
        self._log("▶  " + quote(cmd) + "\n")
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                env=child_env(), creationflags=NO_WINDOW)
        except (FileNotFoundError, OSError) as e:
            self._log(f"Could not start process: {e}")
            return -1
        try:
            for line in self._proc.stdout:
                line = line.rstrip()
                if tidy is not None:
                    try:
                        line = tidy(line)
                    except Exception:
                        pass  # a broken tidier must not hide the real output
                    if line is None:
                        continue
                self._log(line)
                if on_line:
                    try:
                        on_line(line)
                    except Exception:
                        pass  # a bad progress parser must never kill the job
            self._proc.wait()
            return self._proc.returncode
        finally:
            proc, self._proc = self._proc, None
            if self.cancelled and proc and proc.poll() is None:
                proc.terminate()

    # ── Quiet run — used for probes and version checks ───────────────────────

    def probe(self, cmd, timeout=120):
        """Run cmd and capture everything. Never raises; returns a
        CompletedProcess-ish object with .returncode/.stdout/.stderr."""
        try:
            return subprocess.run(
                cmd, capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                env=child_env(), creationflags=NO_WINDOW, timeout=timeout)
        except Exception as e:
            self._log(f"probe failed: {e}")
            return subprocess.CompletedProcess(cmd, -1, "", str(e))

    def cancel(self):
        self.cancelled = True
        proc = self._proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass

    def reset(self):
        self.cancelled = False


# ── Media probing ─────────────────────────────────────────────────────────────

_DUR_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)")


def duration(runner, ffmpeg, path):
    """Length of a media file in seconds, or None. Uses ffmpeg itself so we
    don't have to ship ffprobe as a fourth binary."""
    r = runner.probe([ffmpeg, "-i", path], timeout=60)
    m = _DUR_RE.search((r.stderr or "") + (r.stdout or ""))
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return None


def hhmmss(seconds):
    return (f"{int(seconds // 3600):02d}:"
            f"{int((seconds % 3600) // 60):02d}:"
            f"{seconds % 60:06.3f}")
