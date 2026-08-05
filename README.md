# YT-Pro

A Windows media toolkit with a real GUI. Paste a link, get the file. Paste a
Spotify playlist, get a tagged library. Drop in thirty clips, convert them all.

It's a friendly front end over three excellent command-line tools — **yt-dlp**,
**spotdl** and **ffmpeg** — which it downloads and keeps updated for you. No
Python, no terminal, no `pip install`. One exe.

No telemetry. Nothing is logged, uploaded, or phoned home.

## What it does

**Download** — any of yt-dlp's 1000+ sites: YouTube, Vimeo, X, TikTok,
Instagram, Facebook, Twitch, Reddit, Dailymotion, Rumble, Odysee and the rest.

- Quality from 360p up to 4K, output as MP4, MKV, WEBM, AVI, MOV or FLV
- Audio-only as MP3, M4A, WAV, FLAC, OPUS or OGG, with cover art and tags
- Clip a section without downloading the whole video
- Whole playlists and channels, filed into a folder in order
- Paste a list of links and the lot gets queued

**Music** — Spotify, Apple Music and YouTube Music links, or just a song name.

> Worth being straight about this: Spotify's audio is encrypted and **cannot**
> be downloaded. What actually happens is that the link's track list is read,
> each song is found on YouTube, and then the real title, artist, album, track
> number and cover art are written onto the file. The result is a properly
> tagged library — the audio just doesn't come from Spotify.

**Edit** — trim, split, extract audio, convert, resize, join two files, change
speed. Runs on one file or a whole batch. Reads anything ffmpeg can read, which
in practice means anything: AVI, WMV, MOV, FLV, MPEG, TS, 3GP and the modern
formats too.

**Queue** — everything is a job. One progress bar per item, skip the one you're
bored of, stop the lot, open the output folder when it's done.

## Install

Download `YT-Pro.exe` from Releases and run it. On first launch it fetches
yt-dlp and ffmpeg into `%APPDATA%\YT-Pro` (about 160 MB, once). spotdl is only
fetched if and when you use the Music tab.

If you already have any of those three — via winget, choco, scoop or a manual
install — YT-Pro finds and reuses them instead of downloading its own.

## Run from source

```bash
pip install -r requirements.txt
python main.py
```

Build the exe:

```bash
build.bat
```

Output lands in `dist\YT-Pro.exe`.

## Why it doesn't stop working after a few weeks

Every downloader eventually breaks, and the cause is nearly always the same: the
site changed how it serves video and the bundled yt-dlp is months old. So
YT-Pro runs `yt-dlp -U` in the background on launch, at most once a day, and it
deliberately does **not** bundle yt-dlp into the exe — a bundled copy would be
frozen at build time, which is the whole problem.

The app itself checks GitHub Releases for a newer YT-Pro and offers to swap
itself out.

## Layout

```
main.py                  entry point
ytpro/
├── config.py            settings file, %APPDATA%\YT-Pro paths
├── tools.py             finding, installing and updating the three binaries
├── proc.py              subprocess plumbing: no console flash, cancellable
├── jobs.py              the sequential job queue and its worker thread
├── formats.py           container/codec knowledge (see note below)
├── download.py          yt-dlp command building + progress parsing
├── music.py             spotdl command building + progress parsing
├── edit.py              the ffmpeg operations
└── ui/                  customtkinter — no download or ffmpeg logic in here
    ├── app.py           main window, owns config + queue + the one Tk timer
    ├── download_tab.py  music_tab.py  edit_tab.py  settings_tab.py
    ├── queue_panel.py   logwin.py  setup.py  theme.py
```

Two design notes that matter if you go poking around:

**Format selection is verbose on purpose.** `download.build_format()` repeats the
height cap in every fallback branch, and it never pins a YouTube player client.
Both of those are scar tissue: pinning `player_client=android` makes YouTube
serve only legacy muxed streams, whose "best under 720p" is really the 360p
stream — so a 720p request silently produced 360p.

**Worker threads never touch Tk.** Jobs mutate plain Python state and the UI
polls it on a single timer. Calling Tkinter from a worker can block that worker
inside Tcl, which presents as the queue quietly dying after one job.

## Credit

YT-Pro is a GUI. The actual work is done by
[yt-dlp](https://github.com/yt-dlp/yt-dlp),
[spotdl](https://github.com/spotDL/spotify-downloader) and
[FFmpeg](https://ffmpeg.org/). Please support them.

## Licence

MIT — see [LICENSE](LICENSE).

Download things you have the right to download.
