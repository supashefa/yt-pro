"""YT-Pro — a Windows media toolkit built on yt-dlp, spotdl and ffmpeg."""

__version__ = "1.0.0"

# ── Where the app looks for its own updates ───────────────────────────────────
#
# UPDATE_URL is a plain JSON file on any static host. This is the path to use
# when the code lives in a PRIVATE repo: private release assets need an auth
# token, so the GitHub route can't work, and a static file needs no token, no
# account and gives away nothing about who published it.
#
# Expected shape:
#   {"version": "1.1.0",
#    "url": "https://your-host/YT-Pro.exe",
#    "sha256": "abc123…",            (optional but recommended)
#    "notes": "What changed"}        (optional)
#
# Set UPDATE_URL to "" to disable update checks entirely.
UPDATE_URL = ""

# Alternative route: a PUBLIC GitHub repo's latest release. Only used when
# UPDATE_URL is empty. Left blank by default so a fresh checkout doesn't quietly
# phone a repo that isn't yours.
GITHUB_REPO = ""

APP_NAME = "YT-Pro"
