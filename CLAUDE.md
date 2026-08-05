# YT-Pro — the consolidated project

**This is the live YT-Pro.** It replaces three older folders, all of which are
now dead:

| old folder | what it was | status |
|---|---|---|
| `C:\dev\yt-dlp-drive-divergent` | the previously-newest copy; source of this rewrite | superseded — delete after a week of using this |
| `C:\dev\yt-dlp` | stale April 2026 copy, still had the 360p bug + telemetry | superseded — delete |
| `C:\dev\YT-pro` | unrelated 30-line FastAPI PoC | archived in `_archive/fastapi-poc/` |

Map: `C:\dev\central-hub\maps\yt-pro-app.md`. User-facing docs: `README.md`.

## Run / build

```bash
python main.py           # needs: pip install -r requirements.txt
build.bat                # -> dist\YT-Pro.exe
```

**Ask before running or building.**

Note the entry point is `main.py`, not `ytpro.py` — a module and a package with
the same name in one folder shadow each other and break PyInstaller.

## Architecture in one paragraph

`ytpro/` holds all the logic and imports no Tk. `ytpro/ui/` holds all the Tk and
contains no download or ffmpeg logic. Everything the app does becomes a `Job` on
one sequential `JobQueue` (`jobs.py`), run by a single worker thread that owns
the one `Runner` (`proc.py`) that Cancel targets.

## Invariants — do not regress these

Each of these cost a debugging session. They have comments in the code saying so.

1. **Never pin `--extractor-args youtube:player_client=...`.** Forcing the
   android client makes YouTube return only legacy muxed streams, whose best
   under 720p is really the 360p stream — so "720p" silently downloaded as 360p.
   `download.build_format()` uses yt-dlp's default clients.
2. **Repeat the `height<=N` cap in every fallback branch** of the format
   selector, including the final `best[...]`. Miss one and selection can collapse
   to a tiny muxed stream. There's a test for this — see below.
3. **Worker threads never touch Tk.** Jobs mutate plain state; `App._tick()` is
   the only thing that draws, polling `JobQueue.revision` and the log deque.
   Calling Tk from a worker can block it inside Tcl, which looks like "the queue
   died after one job". This was a real bug, found and fixed.
4. **`self.cfg`, never `self.config`,** on the App. `config` is tkinter's own
   widget method; the old single-file version shadowed it.
5. **Stream copy must fall back to a re-encode** (`edit._attempt`). Verified:
   DivX3+PCM and MS-MPEG4v2+ADPCM AVIs cannot be copied into MP4 and used to
   fail outright.
6. **Don't bundle yt-dlp/ffmpeg/spotdl into the exe.** A bundled yt-dlp is
   frozen at build time, which is precisely the "stops working after a few
   weeks" failure the runtime self-updater exists to prevent. `YT-Pro.spec` has
   a comment about this.
7. **No telemetry, ever.** The predecessor silently POSTed every action to
   `yt-ne.vercel.app/api/log`. It was removed deliberately. Don't add network
   logging of any kind.
8. **`--postprocessor-args` only when not clipping** — it conflicts with
   `--download-sections`.

## Verifying changes

There's no test suite yet. What was used to validate the rewrite (worth
repeating after touching `formats.py`, `edit.py` or `download.py`):

- Assert the height cap appears in every `/`-separated branch of
  `build_format(q, "mp4")` for each non-Best quality.
- Build a real AVI with ffmpeg (`-c:v msmpeg4v3 -c:a pcm_s16le`), run every
  `edit._HANDLERS` op on it, and confirm output files are non-empty.
- Construct `App` with `_first_run` stubbed out, walk every operation's option
  panel and every download mode, and queue a deliberately failing job to check
  it reports `failed` and the next job still runs.

## Known gaps

- The app self-updater points at `GITHUB_REPO` in `ytpro/__init__.py`, which is
  a placeholder until the public repo exists. Until then the check 404s and stays
  silent by design.
- No `assets/ytpro.ico` yet, so the exe uses the default PyInstaller icon.
- 24Six support was discussed and deliberately deferred — the user knows of a
  network-level way to get tracks but it wasn't worth building yet.
- No automated tests, no CI.

## Related

`C:\dev\yiddish-transcribe` — the Whisper + GPT-4o transcription/translation
scripts that used to sit in the old repo. They were unrelated to YT-Pro and
carried a hardcoded OpenAI key; moved out and switched to `.env`.
