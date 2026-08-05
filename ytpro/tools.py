"""Finding, installing and updating the three binaries YT-Pro drives:
yt-dlp.exe, ffmpeg.exe and spotdl.exe.

Two rules shape this module:

1. Never re-download something the user already has. Check our own folder, then
   the app folder, then PATH, then winget's package tree.
2. yt-dlp must keep itself current. Every "YT-Pro stopped working" report is a
   stale yt-dlp after YouTube changed its extraction, so `yt-dlp -U` runs on
   launch (throttled to once a day). spotdl rots the same way and gets the
   same treatment.
"""

import io
import json
import os
import shutil
import time
import urllib.request
import zipfile
from pathlib import Path

from . import GITHUB_REPO, __version__
from .config import TOOLS_DIR, app_dir, save_config

UPDATE_INTERVAL = 86_400          # once per day
_MARKER = TOOLS_DIR / ".last_update_check"

YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
FFMPEG_URL = ("https://github.com/BtbN/FFmpeg-Builds/releases/download/"
              "latest/ffmpeg-master-latest-win64-gpl.zip")
# spotdl publishes a standalone Windows exe with every release. We resolve the
# newest one through the API and fall back to a known-good pin if that fails.
SPOTDL_API = "https://api.github.com/repos/spotDL/spotify-downloader/releases/latest"
SPOTDL_FALLBACK = ("https://github.com/spotDL/spotify-downloader/releases/"
                   "download/v4.5.2/spotdl-4.5.2-win32.exe")

_UA = {"User-Agent": f"YT-Pro/{__version__}"}


# ── Locating tools ────────────────────────────────────────────────────────────

def _resolve(exe_name, extra):
    """First existing path for a tool: the folders we control, then anything on
    PATH (covers winget / choco / scoop / manual installs), then winget's
    package folders."""
    for p in extra:
        try:
            if p.exists():
                return str(p.resolve())
        except OSError:
            pass
    on_path = shutil.which(exe_name)
    if on_path:
        return str(Path(on_path).resolve())
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if base.is_dir():
        try:
            for p in base.rglob(f"{exe_name}.exe"):
                if p.is_file():
                    return str(p.resolve())
        except OSError:
            pass
    return None


def _candidates(name):
    here = app_dir()
    paths = [TOOLS_DIR / f"{name}.exe", here / f"{name}.exe",
             here / "bin" / f"{name}.exe"]
    if name == "ffmpeg":
        # Leftover from how the old repo shipped ffmpeg — still worth checking
        # so upgraders don't get a redundant 140 MB download.
        paths.append(here / "ffmpeg-8.0.1-essentials_build" / "bin" / "ffmpeg.exe")
    return paths


def autodetect(cfg, force=False):
    """Fill in any missing tool paths. Returns True if cfg changed."""
    changed = False
    for key, exe in (("ytdlp", "yt-dlp"), ("ffmpeg", "ffmpeg"), ("spotdl", "spotdl")):
        current = cfg.get(key, "")
        if not force and current and os.path.exists(current):
            continue
        found = _resolve(exe, _candidates(exe))
        if found != current:
            cfg[key] = found or ""
            changed = True
    if changed:
        save_config(cfg)
    return changed


def missing_core(cfg):
    """Which of the two always-needed tools we still have to install. spotdl is
    deliberately excluded — it's only fetched when the Music tab is first used,
    so people who never touch Spotify never pay for the download."""
    out = []
    for key, label in (("ytdlp", "yt-dlp"), ("ffmpeg", "ffmpeg")):
        if not cfg.get(key) or not os.path.exists(cfg[key]):
            out.append(label)
    return out


# ── Installing ────────────────────────────────────────────────────────────────

def _download(url, dest, on_progress=None):
    """Stream a URL to a file, reporting (bytes_done, bytes_total)."""
    tmp = Path(str(dest) + ".part")
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=120) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        with open(tmp, "wb") as fh:
            while True:
                chunk = resp.read(262_144)
                if not chunk:
                    break
                fh.write(chunk)
                done += len(chunk)
                if on_progress:
                    on_progress(done, total)
    tmp.replace(dest)
    return dest


def install_ytdlp(on_progress=None):
    return _download(YTDLP_URL, TOOLS_DIR / "yt-dlp.exe", on_progress)


def install_ffmpeg(on_progress=None):
    """ffmpeg only ships as a zip, and we want exactly one file out of it, so
    this one buffers in memory rather than using _download."""
    req = urllib.request.Request(FFMPEG_URL, headers=_UA)
    chunks, done = [], 0
    with urllib.request.urlopen(req, timeout=180) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        while True:
            chunk = resp.read(262_144)
            if not chunk:
                break
            chunks.append(chunk)
            done += len(chunk)
            if on_progress:
                on_progress(done, total)
    dest = TOOLS_DIR / "ffmpeg.exe"
    with zipfile.ZipFile(io.BytesIO(b"".join(chunks))) as zf:
        for name in zf.namelist():
            if name.endswith("/bin/ffmpeg.exe"):
                dest.write_bytes(zf.read(name))
                return dest
    raise RuntimeError("ffmpeg.exe was not found inside the downloaded archive")


def _spotdl_url():
    try:
        req = urllib.request.Request(SPOTDL_API, headers=_UA)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
        for asset in data.get("assets", []):
            name = asset.get("name", "")
            if name.endswith(".exe") and "win32" in name:
                return asset["browser_download_url"]
    except Exception:
        pass
    return SPOTDL_FALLBACK


def install_spotdl(on_progress=None):
    return _download(_spotdl_url(), TOOLS_DIR / "spotdl.exe", on_progress)


INSTALLERS = {
    "yt-dlp": install_ytdlp,
    "ffmpeg": install_ffmpeg,
    "spotdl": install_spotdl,
}

# Rough sizes, only so the setup window can say something honest up front.
SIZES = {"yt-dlp": "~18 MB", "ffmpeg": "~140 MB", "spotdl": "~46 MB"}


# ── Keeping tools current ─────────────────────────────────────────────────────

def update_due():
    try:
        return not _MARKER.exists() or \
            (time.time() - _MARKER.stat().st_mtime) >= UPDATE_INTERVAL
    except OSError:
        return True


def mark_updated():
    try:
        _MARKER.write_text(str(time.time()), encoding="utf-8")
    except OSError:
        pass


def update_tools(cfg, runner, log, force=False):
    """Self-update yt-dlp and spotdl. Throttled to once a day unless forced.

    Only tools we installed ourselves get updated in place — a yt-dlp that came
    from winget or PATH belongs to whatever installed it, and `-U` on it would
    either fail on permissions or fight the package manager.
    """
    if not force and not update_due():
        return
    ours = str(TOOLS_DIR).lower()
    for key, flag in (("ytdlp", "-U"), ("spotdl", "--download-ffmpeg")):
        path = cfg.get(key) or ""
        if not path or not os.path.exists(path):
            continue
        if not path.lower().startswith(ours):
            log(f"{Path(path).name}: managed elsewhere, skipping self-update")
            continue
        if key == "ytdlp":
            log("Checking for yt-dlp updates…")
            r = runner.probe([path, "-U"], timeout=180)
            out = ((r.stdout or "") + (r.stderr or "")).strip()
            if out:
                log("yt-dlp: " + out.replace("\n", " | "))
        else:
            # spotdl has no -U; replacing the exe from GitHub is the update.
            try:
                log("Checking for a newer spotdl…")
                install_spotdl()
                log("spotdl: up to date")
            except Exception as e:
                log(f"spotdl update failed: {e}")
    mark_updated()


# ── App self-update ───────────────────────────────────────────────────────────

def _newer(remote, local):
    def parts(v):
        return [int(x) for x in v.lstrip("vV").split(".") if x.isdigit()]
    try:
        return parts(remote) > parts(local)
    except Exception:
        return False


def check_app_update(log):
    """Look for a newer YT-Pro release. Returns (tag, download_url) or None.

    Stays completely silent on failure — a private or not-yet-created repo
    returns 404, and that must not look like an error to the user.
    """
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
            headers=_UA)
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.load(resp)
    except Exception:
        return None
    tag = str(data.get("tag_name", ""))
    if not _newer(tag, __version__):
        return None
    for asset in data.get("assets", []):
        if asset.get("name", "").lower().endswith(".exe"):
            log(f"A newer YT-Pro is available: {tag}")
            return tag, asset["browser_download_url"]
    return None


def apply_app_update(url, on_progress=None):
    """Download the new exe next to the running one and hand off to a tiny
    batch script that waits for us to exit, swaps the files and relaunches.

    A running exe can't overwrite itself on Windows, which is why this needs a
    helper process rather than a simple copy.
    """
    import subprocess
    import sys

    if not getattr(sys, "frozen", False):
        raise RuntimeError("Self-update only applies to the packaged exe")

    exe = Path(sys.executable)
    new = exe.with_name(exe.stem + ".new.exe")
    _download(url, new, on_progress)

    script = TOOLS_DIR / "ytpro-update.bat"
    script.write_text(
        "@echo off\r\n"
        "setlocal\r\n"
        f':wait\r\n'
        f'tasklist /fi "PID eq {os.getpid()}" | find "{os.getpid()}" >nul\r\n'
        'if not errorlevel 1 (\r\n'
        '  timeout /t 1 /nobreak >nul\r\n'
        '  goto wait\r\n'
        ')\r\n'
        f'move /y "{new}" "{exe}" >nul\r\n'
        f'start "" "{exe}"\r\n'
        f'del "%~f0"\r\n',
        encoding="utf-8")
    subprocess.Popen(["cmd", "/c", str(script)],
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
