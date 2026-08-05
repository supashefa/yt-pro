"""Building the yt-dlp command line, and reading its progress back.

The format selector here is the single most important piece of logic in the app,
and it is deliberately verbose. See build_format() for why.
"""

import os
import re
from pathlib import Path

from . import formats
from .jobs import Job

PLAYLIST_HINTS = ("list=", "/playlist", "/sets/", "/album/", "/channel/",
                  "/@", "/c/", "/user/")


def looks_like_playlist(url):
    u = url.lower()
    return any(h in u for h in PLAYLIST_HINTS)


# ── Format selection ──────────────────────────────────────────────────────────

def build_format(quality, container):
    """Return the -f expression for a video download.

    Two hard-won rules are encoded here:

    1. Do NOT pin `--extractor-args youtube:player_client=...`. Forcing the
       android client made YouTube hand back only legacy muxed streams, whose
       best under 720p is really the 360p stream — so every "720p" download
       silently came out 360p. yt-dlp's own default clients return the real
       adaptive tracks.

    2. Repeat the height cap in EVERY fallback branch, including the final
       `best[...]`. Miss it in one branch and format selection can quietly
       collapse to a tiny muxed stream — the same failure wearing a different
       hat.
    """
    want_mp4 = container == "mp4"

    if quality == "Best":
        if want_mp4:
            return ("bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]"
                    "/bestvideo[ext=mp4]+bestaudio[ext=m4a]"
                    "/bestvideo+bestaudio/best")
        return "bestvideo+bestaudio/best"

    h = quality.replace("p", "")
    if want_mp4:
        return (f"bestvideo[height<={h}][vcodec^=avc1]+bestaudio[acodec^=mp4a]"
                f"/bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]"
                f"/bestvideo[height<={h}]+bestaudio/best[height<={h}]")
    return f"bestvideo[height<={h}]+bestaudio/best[height<={h}]"


def build_output_template(out_dir, playlist, redownload):
    """Where files land.

    - Playlists get their own subfolder and an index prefix, so a 200-track
      playlist stays in order and doesn't carpet-bomb your Downloads folder.
    - "Re-download" appends the upload date rather than overwriting, so you end
      up with "My Video (2023-05-15).mp4" beside the original instead of losing
      the original.
    """
    if playlist:
        name = "%(playlist_index)03d - %(title)s.%(ext)s"
        return os.path.join(out_dir, "%(playlist_title|Playlist)s", name)
    if redownload:
        return os.path.join(out_dir, "%(title)s (%(upload_date>%Y-%m-%d)s).%(ext)s")
    return os.path.join(out_dir, "%(title)s.%(ext)s")


def build_command(*, ytdlp, ffmpeg, url, out_dir, mode, quality, container,
                  clip_start="", clip_end="", playlist=False, redownload=False,
                  cookies_from_browser=""):
    """Assemble the full yt-dlp argv."""
    fmt = container.lower()
    is_clip = mode == "Clip"
    cmd = [ytdlp, "--newline", "--no-warnings"]

    if ffmpeg and os.path.exists(ffmpeg):
        cmd += ["--ffmpeg-location", str(Path(ffmpeg).parent)]
    if cookies_from_browser:
        cmd += ["--cookies-from-browser", cookies_from_browser]

    cmd += ["--yes-playlist"] if playlist else ["--no-playlist"]

    if mode == "Audio Only":
        af = formats.YTDLP_AUDIO.get(fmt, "mp3")
        cmd += ["-x", "--audio-format", af, "--audio-quality", "0",
                "--embed-thumbnail", "--embed-metadata"]
    else:
        cmd += ["-f", build_format(quality, fmt)]
        if fmt in formats.YTDLP_MERGE:
            cmd += ["--merge-output-format", fmt]
        # Re-encode audio to AAC so MP4s play in Windows Media Player, Edge and
        # on phones. Skipped when clipping, because --postprocessor-args and
        # --download-sections fight each other.
        if fmt == "mp4" and not is_clip:
            cmd += ["--postprocessor-args", "ffmpeg:-c:a aac -b:a 192k"]

    if is_clip:
        s, e = clip_start.strip(), clip_end.strip()
        if s and e:
            cmd += ["--download-sections", f"*{s}-{e}"]
        elif s:
            cmd += ["--download-sections", f"*{s}-inf"]

    cmd += ["-o", build_output_template(out_dir, playlist, redownload), url]
    return cmd


# ── Progress parsing ──────────────────────────────────────────────────────────

_PCT = re.compile(r"\[download\]\s+([\d.]+)%")
_ITEM = re.compile(r"\[download\] Downloading item (\d+) of (\d+)")
_DEST = re.compile(r"\[download\] Destination: .+[/\\](.+?)(?:\.f\d+)?\.\w+$")


class ProgressReader:
    """Turns yt-dlp's stdout into (fraction, human status).

    For a playlist the per-file percentage would jump back to 0 on every track,
    so once we know we're on item N of M we blend the file's own progress into
    that range and the bar only ever moves forward.
    """

    def __init__(self, queue, job):
        self._q = queue
        self._job = job
        self.title = ""
        self._index = 0
        self._total = 0

    def __call__(self, line):
        m = _ITEM.search(line)
        if m:
            self._index, self._total = int(m.group(1)), int(m.group(2))
            self._q.set_detail(self._job, f"item {self._index} of {self._total}")
            return

        m = _PCT.search(line)
        if m:
            frac = float(m.group(1)) / 100
            if self._total:
                frac = ((self._index - 1) + frac) / self._total
                detail = f"{self._index}/{self._total} — {m.group(1)}%"
            else:
                detail = f"{m.group(1)}%"
            self._q.set_progress(self._job, frac, detail)
            return

        if "[Merger]" in line:
            self._q.set_detail(self._job, "merging video + audio…")
        elif "[ExtractAudio]" in line:
            self._q.set_detail(self._job, "extracting audio…")
        elif "[EmbedThumbnail]" in line:
            self._q.set_detail(self._job, "embedding cover art…")
        elif "has already been downloaded" in line:
            self._q.set_detail(self._job, "already downloaded — tick Re-download for a fresh copy")
        else:
            m = _DEST.search(line)
            if m:
                self.title = m.group(1)


# ── Job factory ───────────────────────────────────────────────────────────────

def make_job(*, queue, label, out_dir, **kw):
    def run(job, runner):
        cmd = build_command(out_dir=out_dir, **kw)
        reader = ProgressReader(queue, job)
        rc = runner.run(cmd, on_line=reader)
        if rc != 0 and not runner.cancelled:
            raise RuntimeError("yt-dlp failed — open the log for details")
        return out_dir

    return Job(label=label, kind="download", run=run)
