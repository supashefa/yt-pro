"""Turning "it didn't work" into something you can actually act on.

The constraint that shapes this module: YT-Pro sends nothing anywhere on its
own, and that is not going to change (see the note about telemetry in the
predecessor). So there is no server, no database and no crash uploader here.
What there is instead is a button that packages what you'd otherwise have to
ask for — version, which tools are installed, the tail of the log — and hands
it to the user to send. They can see exactly what they're sending, which is the
only version of this that's honest.

Paths are rewritten before the report leaves the app. A log is full of
C:\\Users\\<their name>\\…, and a public issue tracker is a bad place for that.
"""

import os
import platform
import sys
from pathlib import Path
from urllib.parse import quote

from . import GITHUB_REPO, __version__

# GitHub rejects very long URLs, so the prefilled issue carries only the tail of
# the log. The full text goes to the clipboard and the saved file.
_URL_LOG_LINES = 40
_URL_BUDGET = 6000


def scrub(text):
    """Replace the user's home directory with %USERPROFILE% so a report can be
    posted publicly without handing out someone's name."""
    home = str(Path.home())
    out = text.replace(home, "%USERPROFILE%").replace(
        home.replace("\\", "/"), "%USERPROFILE%")
    # The log quotes paths built by other tools too, which may differ in case.
    lower = home.lower()
    if lower != home:
        out = out.replace(lower, "%USERPROFILE%")
    return out


def system_info(cfg):
    """Everything worth knowing before reading the log itself."""
    tools = []
    for key, name in (("ytdlp", "yt-dlp"), ("ffmpeg", "ffmpeg"),
                      ("spotdl", "spotdl")):
        path = cfg.get(key) or ""
        if path and os.path.exists(path):
            where = "bundled" if str(Path.home()) in path or "YT-Pro" in path \
                else "external"
            tools.append(f"{name}: installed ({where})")
        else:
            tools.append(f"{name}: MISSING")
    deno = Path.home() / ".spotdl" / "deno.exe"
    tools.append(f"deno: {'installed' if deno.exists() else 'MISSING'}")

    return "\n".join([
        f"YT-Pro {__version__}"
        + (" (from source)" if not getattr(sys, "frozen", False) else ""),
        f"Windows {platform.release()} ({platform.version()}) {platform.machine()}",
        f"Python {platform.python_version()}",
        *tools,
    ])


def build_report(cfg, log_lines, note=""):
    """The whole report as plain text — what gets copied and saved."""
    parts = ["## What went wrong", note.strip() or "(describe it here)", "",
             "## System", system_info(cfg), "",
             "## Log", "\n".join(log_lines) or "(log was empty)"]
    return scrub("\n".join(parts))


def issue_url(cfg, log_lines, title="Problem report"):
    """A GitHub 'new issue' link with as much filled in as the URL will hold."""
    tail = list(log_lines)[-_URL_LOG_LINES:]
    body = scrub("\n".join([
        "## What went wrong", "(describe it here)", "",
        "## System", system_info(cfg), "",
        f"## Log (last {len(tail)} lines — full log is on your clipboard, "
        "paste it below)", "```", "\n".join(tail), "```",
    ]))
    while len(quote(body)) > _URL_BUDGET and tail:
        tail = tail[len(tail) // 4 or 1:]
        body = scrub("\n".join([
            "## What went wrong", "(describe it here)", "",
            "## System", system_info(cfg), "",
            "## Log (truncated — full log is on your clipboard, paste it here)",
            "```", "\n".join(tail), "```",
        ]))
    return (f"https://github.com/{GITHUB_REPO}/issues/new"
            f"?title={quote(title)}&body={quote(body)}")


def default_filename():
    return "YT-Pro-report.txt"
