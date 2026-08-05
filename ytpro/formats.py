"""Container and codec knowledge.

This module exists because of a real bug: the old app only offered MP4/MKV/WEBM
as output containers, and every trim/split ran `-c copy` into whatever container
you picked. An AVI usually carries MPEG-4 Part 2 or MJPEG video with MP3 or AC3
audio — none of which MP4 will accept — so stream-copying an AVI into an .mp4
just failed, and the user saw "Something went wrong".

The fix is two-part and lives here:
  1. Offer the containers ffmpeg can actually write (AVI, MOV, FLV, OGG… ).
  2. Know a correct codec pair for each container, so when a stream copy is
     refused we can retry with a re-encode that the container will accept.
"""

# ── What the UI offers ────────────────────────────────────────────────────────

SAME_AS_INPUT = "Same as input"

# Containers ffmpeg writes happily and that people actually ask for.
VIDEO_CONTAINERS = ["MP4", "MKV", "WEBM", "AVI", "MOV", "FLV"]
AUDIO_CONTAINERS = ["MP3", "M4A", "WAV", "FLAC", "OPUS", "OGG"]

# yt-dlp's --merge-output-format only accepts these. Handily, it's every video
# container we offer, so the download tab needs no special-casing.
YTDLP_MERGE = {"mp4", "mkv", "webm", "avi", "mov", "flv"}

# yt-dlp's --audio-format names. Note OGG maps to "vorbis", not "ogg".
YTDLP_AUDIO = {
    "mp3": "mp3", "m4a": "m4a", "wav": "wav",
    "flac": "flac", "opus": "opus", "ogg": "vorbis", "aac": "aac",
}

DOWNLOAD_QUALITIES = ["Best", "2160p", "1440p", "1080p", "720p", "480p", "360p"]
RESIZE_HEIGHTS = ["2160p", "1440p", "1080p", "720p", "480p", "360p", "240p"]

# Only H.264 is reliably available up to 1080p. Above that, YouTube serves VP9
# or AV1 only — so an MP4 request at 1440p/2160p gets a VP9 stream muxed into
# MP4, which most players handle but some old ones don't. The UI warns instead
# of silently downgrading, because silently downgrading is exactly the bug we
# just spent a session fixing.
H264_CEILING = 1080

# Anything ffmpeg has a demuxer for is fair game as *input*. The picker leads
# with a broad list and always offers "All files", so an unlisted format still
# works — it just isn't advertised.
INPUT_PATTERNS = (
    "*.mp4 *.mkv *.webm *.avi *.mov *.m4v *.mpg *.mpeg *.wmv *.flv *.3gp *.ts "
    "*.m2ts *.vob *.ogv *.mxf *.divx *.asf *.rm *.rmvb "
    "*.mp3 *.m4a *.aac *.wav *.flac *.opus *.ogg *.oga *.wma *.aiff *.alac *.amr"
)
INPUT_FILETYPES = [("Media files", INPUT_PATTERNS), ("All files", "*.*")]

AUDIO_EXTS = {"mp3", "m4a", "aac", "wav", "flac", "opus", "ogg", "oga",
              "wma", "aiff", "alac", "amr", "ac3", "dts", "ape", "m4b"}


def is_audio_container(fmt):
    return fmt.lower() in {c.lower() for c in AUDIO_CONTAINERS} or \
        fmt.lower() in AUDIO_EXTS


# ── Codec pairs per container, for the re-encode fallback ─────────────────────
#
# Chosen for compatibility over efficiency: the point of a fallback is that the
# file plays, not that it's small.

_VIDEO_CODECS = {
    "mp4":  ["-c:v", "libx264", "-preset", "medium", "-crf", "21",
             "-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    "mov":  ["-c:v", "libx264", "-preset", "medium", "-crf", "21",
             "-pix_fmt", "yuv420p"],
    "mkv":  ["-c:v", "libx264", "-preset", "medium", "-crf", "21",
             "-pix_fmt", "yuv420p"],
    # FLV only accepts a short list of codecs; H.264 + AAC is the safe pair.
    "flv":  ["-c:v", "libx264", "-preset", "medium", "-crf", "21",
             "-pix_fmt", "yuv420p"],
    # AVI predates H.264 as far as most AVI-era players are concerned. MPEG-4
    # Part 2 is what those players expect, and ffmpeg's mpeg4 encoder is
    # always present in a standard build.
    "avi":  ["-c:v", "mpeg4", "-vtag", "DX50", "-q:v", "4"],
    "webm": ["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-row-mt", "1"],
}

_AUDIO_CODECS = {
    "mp4":  ["-c:a", "aac", "-b:a", "192k"],
    "mov":  ["-c:a", "aac", "-b:a", "192k"],
    "mkv":  ["-c:a", "aac", "-b:a", "192k"],
    "flv":  ["-c:a", "aac", "-b:a", "192k"],
    "avi":  ["-c:a", "libmp3lame", "-q:a", "2"],
    "webm": ["-c:a", "libopus", "-b:a", "160k"],
    # Audio-only containers.
    "mp3":  ["-c:a", "libmp3lame", "-q:a", "2"],
    "m4a":  ["-c:a", "aac", "-b:a", "192k"],
    "aac":  ["-c:a", "aac", "-b:a", "192k"],
    "wav":  ["-c:a", "pcm_s16le"],
    "flac": ["-c:a", "flac"],
    "opus": ["-c:a", "libopus", "-b:a", "160k"],
    "ogg":  ["-c:a", "libvorbis", "-q:a", "5"],
}


def video_encode_args(container):
    """ffmpeg args to re-encode video+audio into `container`."""
    c = container.lower()
    return _VIDEO_CODECS.get(c, _VIDEO_CODECS["mp4"]) + \
        _AUDIO_CODECS.get(c, _AUDIO_CODECS["mp4"])


def audio_encode_args(container):
    """ffmpeg args to re-encode audio into `container`."""
    return _AUDIO_CODECS.get(container.lower(), _AUDIO_CODECS["mp3"])


def resolve_output_ext(chosen, input_path):
    """Turn the dropdown value into a real extension. 'Same as input' is the
    sane default for trimming and splitting — it's what makes stream-copy
    succeed on the first try instead of needing the fallback."""
    if chosen == SAME_AS_INPUT:
        ext = str(input_path).rsplit(".", 1)[-1].lower()
        return ext if ext and len(ext) <= 5 else "mp4"
    return chosen.lower()
