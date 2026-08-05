"""Spotify / Apple Music / YouTube Music support, via spotdl.

Worth being clear about what this does, because the naive expectation is wrong:
**nothing downloads audio from Spotify.** Spotify's streams are encrypted and
there is no way around that. What spotdl does — and what every working tool
does — is read the track list from the link's metadata, find each song on
YouTube, download that audio, and then write the real title, artist, album,
track number and cover art onto the file from the Spotify metadata.

So the result is a properly tagged library that came from YouTube. That's the
honest description, and it's genuinely what people want.

spotdl also accepts Apple Music and YouTube Music links, so this tab doubles as
the "music with correct tags" path for those.
"""

import os
import re

from .jobs import Job

AUDIO_FORMATS = ["MP3", "M4A", "FLAC", "OPUS", "WAV"]
BITRATES = ["Best available", "320k", "256k", "192k", "128k"]

# Folder layout options — spotdl's own template syntax.
LAYOUTS = {
    "Artist / Album / Track":  "{artist}/{album}/{track-number} - {title}.{output-ext}",
    "Artist / Track":          "{artist}/{title}.{output-ext}",
    "Flat (Artist - Track)":   "{artist} - {title}.{output-ext}",
}

SUPPORTED_HINT = (
    "Spotify tracks, albums, playlists and artists · Apple Music · "
    "YouTube Music · plain search terms"
)


def build_command(*, spotdl, ffmpeg, url, out_dir, audio_format="mp3",
                  bitrate="", layout=None, threads=4):
    cmd = [spotdl, "download", url]
    cmd += ["--output", os.path.join(out_dir, layout or list(LAYOUTS.values())[0])]
    cmd += ["--format", audio_format.lower()]
    if bitrate and bitrate != "Best available":
        cmd += ["--bitrate", bitrate]
    if ffmpeg and os.path.exists(ffmpeg):
        cmd += ["--ffmpeg", ffmpeg]
    cmd += ["--threads", str(threads)]
    # Keep spotdl from trying to manage its own ffmpeg — ours is already sorted.
    cmd += ["--print-errors"]
    return cmd


# ── Progress parsing ──────────────────────────────────────────────────────────
#
# spotdl has no machine-readable progress, so we count. "Found N songs" gives
# the denominator and each "Downloaded ..." line advances the numerator. If the
# denominator never appears (single track), the bar just pulses on each line.

_FOUND = re.compile(r"Found (\d+) songs?", re.I)
_DOWNLOADED = re.compile(r'^Downloaded\s+"(.+?)"', re.I)
_SKIPPED = re.compile(r"Skipping (.+?) \(", re.I)


class ProgressReader:
    def __init__(self, queue, job):
        self._q = queue
        self._job = job
        self.total = 0
        self.done = 0
        self.failed = 0

    def __call__(self, line):
        m = _FOUND.search(line)
        if m:
            self.total = int(m.group(1))
            self._q.set_detail(self._job, f"found {self.total} tracks")
            return

        m = _DOWNLOADED.search(line)
        if m:
            self.done += 1
            self._advance(m.group(1))
            return

        m = _SKIPPED.search(line)
        if m:
            self.done += 1
            self._advance(f"{m.group(1)} (already there)")
            return

        if "LookupError" in line or "AudioProviderError" in line:
            self.failed += 1

    def _advance(self, name):
        if self.total:
            frac = self.done / self.total
            self._q.set_progress(
                self._job, frac, f"{self.done}/{self.total} — {name[:48]}")
        else:
            self._q.set_detail(self._job, name[:60])


# ── Job factory ───────────────────────────────────────────────────────────────

def make_job(*, queue, label, out_dir, **kw):
    def run(job, runner):
        cmd = build_command(out_dir=out_dir, **kw)
        reader = ProgressReader(queue, job)
        rc = runner.run(cmd, on_line=reader)
        if runner.cancelled:
            return out_dir
        # spotdl exits 0 even when individual tracks couldn't be matched, so a
        # non-zero code means something structural went wrong.
        if rc != 0:
            raise RuntimeError("spotdl failed — open the log for details")
        if reader.failed:
            queue.set_detail(
                job, f"done — {reader.failed} track(s) had no match, see log")
        return out_dir

    return Job(label=label, kind="music", run=run)
