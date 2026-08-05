"""Config file and the folder where YT-Pro keeps its own copies of the tools."""

import json
import os
import sys
from pathlib import Path

# Tools live in AppData\YT-Pro — out of the way, but always findable and always
# writable, which matters because we self-update the binaries in place.
TOOLS_DIR = Path(os.environ.get("APPDATA", Path.home())) / "YT-Pro"
TOOLS_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = Path.home() / ".ytpro_config.json"

DEFAULTS = {
    "ytdlp": "",
    "ffmpeg": "",
    "spotdl": "",
    "download_dir": str(Path.home() / "Downloads"),
    "music_dir": str(Path.home() / "Music"),
    "check_app_updates": True,
}


def load_config():
    if CONFIG_FILE.exists():
        try:
            return {**DEFAULTS, **json.loads(CONFIG_FILE.read_text(encoding="utf-8"))}
        except Exception:
            pass
    return dict(DEFAULTS)


def save_config(cfg):
    try:
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception:
        pass


def app_dir():
    """Folder the app is running from — the exe's folder when frozen, the
    package's parent when running from source. Used to find tools shipped
    alongside the app."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent
