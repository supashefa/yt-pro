"""YT-Pro — a Windows media toolkit built on yt-dlp, spotdl and ffmpeg."""

__version__ = "1.0.0"

# ── Where the app looks for its own updates ───────────────────────────────────
#
# The app checks this repo's latest GitHub release on launch (once a day) and
# offers to update itself if the tag is newer than __version__ above.
#
# IMPORTANT: this must match the real repo, owner and name both. If it doesn't,
# the check quietly 404s and nobody ever gets an update — it fails silent by
# design, so a wrong value here looks exactly like "no updates available".
GITHUB_REPO = "supashefa/yt-pro"

# Alternative route for a private repo, where release assets need an auth token
# that the app doesn't have. Point this at a static JSON file instead and it
# takes precedence over GITHUB_REPO:
#   {"version": "1.1.0", "url": "https://host/YT-Pro.exe", "sha256": "…"}
# Empty means "use GITHUB_REPO".
UPDATE_URL = ""

APP_NAME = "YT-Pro"
