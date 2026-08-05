"""The ffmpeg-backed editing operations.

The important change from the old version is `_attempt`: every operation that
could get away with a stream copy tries that first, and **falls back to a
re-encode if the container refuses the codecs** instead of just reporting
"something went wrong".

That single behaviour is what makes AVI, WMV, FLV and MOV work. An AVI carrying
MPEG-4 Part 2 video and MP3 audio cannot be stream-copied into an .mp4 — MP4 has
no place to put those streams. The old code ran `-c copy` unconditionally, so it
failed. Now the copy is attempted, ffmpeg says no, and we re-encode with codecs
the target container actually accepts.
"""

import os
import re
from pathlib import Path

from . import formats
from .jobs import Job
from .proc import duration, hhmmss

OPERATIONS = [
    "Trim",
    "Split in Half",
    "Extract Audio",
    "Convert Format",
    "Compress / Resize",
    "Combine Files",
    "Change Speed",
]


_TIME = re.compile(r"time=(\d+):(\d+):([\d.]+)")


class _Progress:
    """ffmpeg prints `time=00:01:23.45` as it works. Against a known duration
    that gives a real percentage, which beats a spinner."""

    def __init__(self, queue, job, total, label=""):
        self._q, self._job = queue, job
        self._total = total or 0
        self._label = label

    def __call__(self, line):
        m = _TIME.search(line)
        if not m or not self._total:
            return
        secs = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        frac = min(0.99, secs / self._total)
        pretty = f"{int(secs // 60)}:{int(secs % 60):02d}"
        self._q.set_progress(
            self._job, frac,
            f"{self._label}{pretty} of {int(self._total // 60)}:{int(self._total % 60):02d}")


class Ctx:
    """Everything an operation needs, bundled so the signatures stay short."""

    def __init__(self, *, ffmpeg, queue, job, runner, log):
        self.ffmpeg = ffmpeg
        self.queue = queue
        self.job = job
        self.runner = runner
        self.log = log
        self._duration = None

    def duration(self, path):
        if self._duration is None:
            self._duration = duration(self.runner, self.ffmpeg, path)
        return self._duration

    def progress(self, total, label=""):
        return _Progress(self.queue, self.job, total, label)

    def status(self, text):
        self.queue.set_detail(self.job, text)


def _attempt(ctx, *, pre, post_copy, post_encode, out, total, label=""):
    """Run `pre + post_copy + [out]`, and on failure retry with post_encode.

    `pre` is everything before the codec flags (input, seek, filters); `post_*`
    are the two codec choices.
    """
    if post_copy is not None:
        ctx.status("copying streams…")
        rc = ctx.runner.run(pre + post_copy + [out],
                            on_line=ctx.progress(total, label))
        if rc == 0:
            return out
        if ctx.runner.cancelled:
            return out
        ctx.log("Stream copy was refused by the output container — "
                "re-encoding instead. This is normal for AVI, WMV and FLV.")
        ctx.status("re-encoding (the container needs it)…")
        _unlink(out)

    rc = ctx.runner.run(pre + post_encode + [out],
                        on_line=ctx.progress(total, label))
    if rc != 0 and not ctx.runner.cancelled:
        raise RuntimeError("ffmpeg failed — open the log for details")
    return out


def _unlink(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _out_path(out_dir, stem, suffix, ext):
    return os.path.join(out_dir, f"{stem}{suffix}.{ext}")


# ── The operations ────────────────────────────────────────────────────────────

def _trim(ctx, p):
    src, ext = p["input"], p["ext"]
    out = _out_path(p["out_dir"], Path(src).stem, "_trimmed", ext)
    start = (p.get("start") or "0").strip() or "0"
    end = (p.get("end") or "").strip()

    pre = [ctx.ffmpeg, "-y", "-i", src, "-ss", start]
    if end:
        pre += ["-to", end]
    return _attempt(ctx, pre=pre,
                    post_copy=["-c", "copy"],
                    post_encode=formats.video_encode_args(ext)
                    if not formats.is_audio_container(ext)
                    else formats.audio_encode_args(ext),
                    out=out, total=ctx.duration(src))


def _split(ctx, p):
    src, ext = p["input"], p["ext"]
    total = ctx.duration(src)
    if not total:
        raise RuntimeError("Could not read the file's duration")
    mid = hhmmss(total / 2)
    stem = Path(src).stem
    o1 = _out_path(p["out_dir"], stem, "_part1", ext)
    o2 = _out_path(p["out_dir"], stem, "_part2", ext)
    ctx.log(f"Splitting at {mid}\n")

    enc = (formats.audio_encode_args(ext) if formats.is_audio_container(ext)
           else formats.video_encode_args(ext))
    _attempt(ctx, pre=[ctx.ffmpeg, "-y", "-i", src, "-to", mid],
             post_copy=["-c", "copy"], post_encode=enc,
             out=o1, total=total / 2, label="part 1 — ")
    _attempt(ctx, pre=[ctx.ffmpeg, "-y", "-i", src, "-ss", mid],
             post_copy=["-c", "copy"], post_encode=enc,
             out=o2, total=total / 2, label="part 2 — ")
    return f"{o1}\n{o2}"


def _extract_audio(ctx, p):
    src = p["input"]
    ext = p["ext"] if formats.is_audio_container(p["ext"]) else "mp3"
    out = _out_path(p["out_dir"], Path(src).stem, "", ext)
    return _attempt(ctx, pre=[ctx.ffmpeg, "-y", "-i", src, "-vn"],
                    post_copy=None,
                    post_encode=formats.audio_encode_args(ext),
                    out=out, total=ctx.duration(src))


def _convert(ctx, p):
    src, ext = p["input"], p["ext"]
    out = _out_path(p["out_dir"], Path(src).stem, "", ext)
    if os.path.abspath(out) == os.path.abspath(src):
        out = _out_path(p["out_dir"], Path(src).stem, "_converted", ext)
    audio_out = formats.is_audio_container(ext)
    pre = [ctx.ffmpeg, "-y", "-i", src] + (["-vn"] if audio_out else [])
    enc = (formats.audio_encode_args(ext) if audio_out
           else formats.video_encode_args(ext))
    return _attempt(ctx, pre=pre, post_copy=None, post_encode=enc,
                    out=out, total=ctx.duration(src))


def _compress(ctx, p):
    src, ext = p["input"], p["ext"]
    if formats.is_audio_container(ext):
        raise RuntimeError("Pick a video format to resize into")
    height = p["height"].replace("p", "")
    out = _out_path(p["out_dir"], Path(src).stem, f"_{height}p", ext)
    # scale=-2 keeps the aspect ratio and forces an even width, which every
    # H.264 and VP9 encoder requires.
    pre = [ctx.ffmpeg, "-y", "-i", src, "-vf", f"scale=-2:{height}"]
    # The old version used `-c:a copy` here, which broke the moment the source
    # carried audio the target container wouldn't take. Re-encoding the audio is
    # cheap next to the video pass.
    return _attempt(ctx, pre=pre, post_copy=None,
                    post_encode=formats.video_encode_args(ext),
                    out=out, total=ctx.duration(src))


def _combine(ctx, p):
    src, ext = p["input"], p["ext"]
    second = (p.get("second") or "").strip()
    if not second or not os.path.exists(second):
        raise RuntimeError("Pick a second file to join on")
    out = _out_path(p["out_dir"], Path(src).stem, "_combined", ext)
    audio_out = formats.is_audio_container(ext)

    if audio_out:
        filt = "[0:a][1:a]concat=n=2:v=0:a=1[a]"
        maps = ["-map", "[a]"]
    else:
        filt = "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]"
        maps = ["-map", "[v]", "-map", "[a]"]

    pre = [ctx.ffmpeg, "-y", "-i", src, "-i", second,
           "-filter_complex", filt] + maps
    total = (ctx.duration(src) or 0) + (duration(ctx.runner, ctx.ffmpeg, second) or 0)
    enc = (formats.audio_encode_args(ext) if audio_out
           else formats.video_encode_args(ext))
    return _attempt(ctx, pre=pre, post_copy=None, post_encode=enc,
                    out=out, total=total)


def _atempo_chain(speed):
    """ffmpeg's atempo filter only accepts 0.5–2.0, so anything outside that
    range has to be built from a chain of doublings or halvings."""
    parts, s = [], speed
    while s > 2.0:
        parts.append("atempo=2.0")
        s /= 2.0
    while s < 0.5:
        parts.append("atempo=0.5")
        s *= 2.0
    parts.append(f"atempo={s:.4f}")
    return ",".join(parts)


def _speed(ctx, p):
    src, ext = p["input"], p["ext"]
    try:
        spd = max(0.25, min(4.0, float(str(p["speed"]).strip())))
    except (TypeError, ValueError):
        raise RuntimeError("Enter a speed like 1.5 or 2.0")
    out = _out_path(p["out_dir"], Path(src).stem, f"_{spd:g}x", ext)
    audio_out = formats.is_audio_container(ext)

    if audio_out:
        pre = [ctx.ffmpeg, "-y", "-i", src, "-vn",
               "-filter:a", _atempo_chain(spd)]
        enc = formats.audio_encode_args(ext)
    else:
        pre = [ctx.ffmpeg, "-y", "-i", src, "-filter_complex",
               f"[0:v]setpts={1 / spd:.6f}*PTS[v];[0:a]{_atempo_chain(spd)}[a]",
               "-map", "[v]", "-map", "[a]"]
        enc = formats.video_encode_args(ext)

    total = ctx.duration(src)
    return _attempt(ctx, pre=pre, post_copy=None, post_encode=enc,
                    out=out, total=(total / spd) if total else None)


_HANDLERS = {
    "Trim": _trim,
    "Split in Half": _split,
    "Extract Audio": _extract_audio,
    "Convert Format": _convert,
    "Compress / Resize": _compress,
    "Combine Files": _combine,
    "Change Speed": _speed,
}


# ── Job factory ───────────────────────────────────────────────────────────────

def make_job(*, queue, ffmpeg, log, op, params):
    """One job per input file — that's what makes batch editing work: drop in
    twenty files and you get twenty queued jobs with individual status."""
    src = params["input"]
    label = f"{op} — {Path(src).name}"

    def run(job, runner):
        ctx = Ctx(ffmpeg=ffmpeg, queue=queue, job=job, runner=runner, log=log)
        handler = _HANDLERS.get(op)
        if handler is None:
            raise RuntimeError(f"Unknown operation: {op}")
        if not os.path.exists(src):
            raise RuntimeError("Input file no longer exists")
        os.makedirs(params["out_dir"], exist_ok=True)
        return handler(ctx, params)

    return Job(label=label, kind="edit", run=run)
