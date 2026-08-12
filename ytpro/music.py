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
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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
    "YouTube Music · plain search terms · YouTubeURL|SpotifyURL to pick the "
    "audio yourself"
)

# Where the audio is looked for, in order. YouTube Music first because its
# matches carry the best metadata, then plain YouTube, then the two that
# actually rescue things: a lot of independent music — Jewish music very much
# included — is on Bandcamp or SoundCloud and was never uploaded to YouTube at
# all. Falling through costs nothing when the first provider succeeds.
AUDIO_PROVIDERS = ["youtube-music", "youtube", "soundcloud", "bandcamp"]


# ── Link cleaning ─────────────────────────────────────────────────────────────
#
# Share buttons append tracking parameters, and spotdl chokes on them: a
# music.youtube.com link with "&si=..." on the end returns "Could not get
# metadata for YouTube Music link, skipping" and downloads nothing, while the
# same link without it resolves fine. Verified both ways. Since every share
# button on a phone produces the version that fails, this has to be handled
# here rather than asked of the user.

# Parameters that actually identify something. Everything else is tracking.
_KEEP_PARAMS = {"v", "list"}
_SITES = ("spotify.com", "youtube.com", "youtu.be", "music.apple.com")


def clean_url(text):
    """Strip tracking parameters from a music link. Anything that isn't a link
    to a site we know — a search phrase, say — comes back untouched."""
    text = text.strip()
    # "YouTubeURL|SpotifyURL" picks the audio by hand; both halves need it.
    if "|" in text:
        return "|".join(clean_url(part) for part in text.split("|", 1))
    if not text.lower().startswith(("http://", "https://")):
        return text
    parts = urlsplit(text)
    if not any(parts.netloc.lower().endswith(s) for s in _SITES):
        return text
    kept = [(k, v) for k, v in parse_qsl(parts.query) if k in _KEEP_PARAMS]
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(kept), ""))


def build_command(*, spotdl, ffmpeg, url, out_dir, audio_format="mp3",
                  bitrate="", layout=None, threads=4, loose=False):
    cmd = [spotdl, "download", clean_url(url)]
    cmd += ["--output", os.path.join(out_dir, layout or list(LAYOUTS.values())[0])]
    cmd += ["--format", audio_format.lower()]
    if bitrate and bitrate != "Best available":
        cmd += ["--bitrate", bitrate]
    if ffmpeg and os.path.exists(ffmpeg):
        cmd += ["--ffmpeg", ffmpeg]
    cmd += ["--audio"] + AUDIO_PROVIDERS
    if loose:
        # Drops spotdl's title/artist/duration filter. This is what finds songs
        # whose transliteration doesn't match — "Naar Hayisi" vs "Naar Hoyisi"
        # vs the Hebrew — but with the filter off a cover, a live version or a
        # two-hour mix can come back instead. Deliberately opt-in.
        cmd += ["--dont-filter-results"]
    cmd += ["--threads", str(threads)]
    # Keep spotdl from trying to manage its own ffmpeg — ours is already sorted.
    cmd += ["--print-errors"]
    # ── Do not remove. This is what makes non-Latin names survive. ────────────
    # spotdl's default TUI is rich, and because we read its output through a
    # pipe, rich decides it's on a legacy Windows console and renders through
    # colorama, which encodes with the system code page — cp1252 here. Any
    # Hebrew title or artist then raises UnicodeEncodeError *inside rich's own
    # final buffer flush*, which escapes as an unhandled exception and takes
    # spotdl down with a non-zero exit. Measured: a Hebrew-titled song that
    # downloaded perfectly still exited 1, so the app reported the whole album
    # as failed. --simple-tui skips rich's live display; the same names then
    # only reach the logger, whose encode errors logging swallows. Verified
    # against both a Hebrew album that matches nothing and one that downloads.
    #
    # Setting PYTHONIOENCODING/PYTHONUTF8 on the child does NOT fix this —
    # spotdl.exe is a PyInstaller build and ignores both. Also tested.
    cmd += ["--simple-tui"]
    return cmd


# ── Progress parsing ──────────────────────────────────────────────────────────
#
# spotdl has no machine-readable progress, so we count. "Found N songs" gives
# the denominator and each "Downloaded ..." line advances the numerator. If the
# denominator never appears (single track), the bar just pulses on each line.

_FOUND = re.compile(r"Found (\d+) songs?", re.I)
_DOWNLOADED = re.compile(r'^Downloaded\s+"(.+?)"', re.I)
_SKIPPED = re.compile(r"Skipping (.+?) \(", re.I)
# spotdl reports the same miss twice — once as it happens, and again in the
# --print-errors summary with the Spotify URL glued on the front. Both end in
# the song name, so keying on the name is what stops one failure counting as
# two.
_NO_MATCH = re.compile(r"No results found for song:\s*(.+?)\s*$", re.I)
_PROVIDER_ERR = re.compile(r"AudioProviderError:\s*(.+?)\s*$", re.I)


class ProgressReader:
    def __init__(self, queue, job):
        self._q = queue
        self._job = job
        self.total = 0
        self.done = 0
        self.misses = []          # song names with no match on any provider
        self.errors = []          # found, but the download itself failed

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

        # Two different failures that must not be described the same way: no
        # provider had the song at all, versus the download of a song we did
        # find going wrong.
        m = _NO_MATCH.search(line)
        if m:
            if m.group(1) not in self.misses:
                self.misses.append(m.group(1))
            return

        m = _PROVIDER_ERR.search(line)
        if m:
            if m.group(1) not in self.errors:
                self.errors.append(m.group(1))

    @property
    def failed(self):
        return len(self.misses) + len(self.errors)

    def _advance(self, name):
        if self.total:
            frac = self.done / self.total
            self._q.set_progress(
                self._job, frac, f"{self.done}/{self.total} — {name[:48]}")
        else:
            self._q.set_detail(self._job, name[:60])


# ── Making spotdl's crash noise readable ──────────────────────────────────────
#
# --simple-tui stops the encode failure from killing spotdl, but it doesn't stop
# it happening: printing a Hebrew name still fails, and Python's logging prints
# a forty-line "--- Logging error ---" block when a handler raises. That block
# is not noise to be thrown away, though. It ends with the message and the
# arguments logging *would* have printed:
#
#   Message: 'Downloaded "%s": %s'
#   Arguments: ('נפתלי - Letaken Olam', 'https://…')
#
# So the download we can't see reported is right there. Recovering it turns
# forty lines of traceback into the one line that was meant to be printed, and —
# this is the part that matters — lets the progress counter see the successes
# and misses that would otherwise be invisible for every non-Latin title.

_BLOCK_START = "--- Logging error ---"
_MSG = re.compile(r"^Message:\s*(.+)$")
_ARGS = re.compile(r"^Arguments:\s*(.+)$")
_QUOTED = re.compile(r"'((?:[^'\\]|\\.)*)'")
_ESCAPED = re.compile(r"\\u[0-9a-fA-F]{4}")


def _unescape(text):
    """Turn the \\uXXXX escapes logging leaves behind back into real text."""
    if not _ESCAPED.search(text):
        return text
    try:
        return text.encode("ascii", "backslashreplace").decode("unicode_escape")
    except Exception:
        return text


class LogTidy:
    """Collapses each logging-error block into the single line it was trying to
    print. Everything outside a block passes through untouched."""

    def __init__(self):
        self._in_block = False
        self._message = ""

    def __call__(self, line):
        if line.startswith(_BLOCK_START):
            self._in_block = True
            self._message = ""
            return None
        if not self._in_block:
            return line

        m = _MSG.match(line)
        if m:
            self._message = m.group(1).strip()
            return None

        m = _ARGS.match(line)
        if m:
            self._in_block = False
            return self._rebuild(m.group(1).strip())

        return None  # traceback body — drop it

    def _rebuild(self, args_text):
        msg = _unescape(self._message.strip("'\""))
        values = [_unescape(v) for v in _QUOTED.findall(args_text)]
        # Arguments can hold an exception rather than a string, in which case
        # the quoted pieces are its message. Formatting only when the count
        # lines up keeps a surprise from turning into a wrong line.
        if msg.count("%s") == len(values):
            try:
                return msg % tuple(values)
            except Exception:
                pass
        if values:
            return ": ".join(values) if msg.count("%s") > 1 else values[-1]
        return None


# ── Job factory ───────────────────────────────────────────────────────────────

def make_job(*, queue, label, out_dir, cfg=None, **kw):
    def run(job, runner):
        # Deno normally arrives with the daily tool check, but someone who
        # installs spotdl and downloads immediately would otherwise spend their
        # first album wondering why half the tracks fail. Costs one file-exists
        # check once it's there. Imported here, not at module scope, to keep
        # this module free of the installer's imports.
        if cfg is not None:
            from . import tools
            try:
                tools.ensure_deno(cfg, runner, runner.log)
            except Exception:
                pass  # never block a download over an optional helper
        cmd = build_command(out_dir=out_dir, **kw)
        reader = ProgressReader(queue, job)
        rc = runner.run(cmd, on_line=reader, tidy=LogTidy())
        if runner.cancelled:
            return out_dir

        # "No results found" is not a broken tool, it's a song that isn't on any
        # of the providers — usually because the release was never uploaded
        # anywhere but Spotify. Say that, rather than "spotdl failed", which
        # sends people looking for a bug that isn't there.
        if reader.done == 0 and reader.failed:
            raise RuntimeError(_failure_message(reader))
        # Past that, spotdl exits 0 even when individual tracks were missed, so
        # a non-zero code really does mean something structural went wrong.
        if rc != 0:
            raise RuntimeError("spotdl failed — open the log for details")
        if reader.failed:
            names = ", ".join(reader.misses + reader.errors)
            queue.set_detail(
                job, f"done — {reader.done} of {reader.total or '?'} saved; "
                     f"skipped {names[:70]}")
        return out_dir

    return Job(label=label, kind="music", run=run)


def _failure_message(reader):
    """Nothing was saved. Say which of the two reasons it was."""
    if reader.errors and not reader.misses:
        return (f"found the audio but the download failed "
                f"({len(reader.errors)} track(s)) — see the log")
    where = "YouTube, SoundCloud or Bandcamp"
    if len(reader.misses) == 1:
        return f"{reader.misses[0]} is not on {where} — nothing downloaded"
    return (f"none of these {len(reader.misses)} tracks are on {where} — "
            f"nothing downloaded. Try 'Search harder', or paste "
            f"YouTubeURL|SpotifyURL to choose the audio yourself")
