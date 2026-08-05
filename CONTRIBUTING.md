# Contributing

Ideas and bug reports are genuinely welcome. Use **Issues** for problems and
**Discussions** for questions and suggestions.

## Reporting a bug

The single most useful thing you can include is the log. Click **View log** in
the app, then **Copy all**, and paste it in. It shows the exact command that ran
and what the tool said back, which usually makes the cause obvious.

Also mention:

- What you clicked, and what you expected instead
- The link or file type involved (a link you can share helps a lot)
- Your Windows version

**Do not paste a log containing a private or unlisted URL** if you'd rather not
share it — trim that line out first.

## Before filing: is it actually YT-Pro?

A lot of "it stopped working" turns out to be a site changing how it serves
video, which is a yt-dlp matter rather than a YT-Pro one. Quick check:

1. Settings → **Update tools now**, then try again.
2. Still broken? Open a terminal in `%APPDATA%\YT-Pro` and run
   `yt-dlp.exe -F "your-link"`. If that fails too, the issue belongs upstream at
   [yt-dlp](https://github.com/yt-dlp/yt-dlp/issues) and they'll fix it far
   faster than I can.

Report it here if the command-line tool works but YT-Pro doesn't. That's a real
bug in this project.

## Pull requests

Small, focused PRs get merged. Large ones that rework several things at once are
hard to review and tend to stall.

The layout matters: **`ytpro/` holds logic and imports no Tk. `ytpro/ui/` holds
Tk and holds no download or ffmpeg logic.** Keeping that line clean is what
makes the code testable, so please don't cross it.

Please also run `python -m pyflakes ytpro main.py` before opening a PR.

## Things that will be rejected

Not to be difficult — each of these is a bug that already happened here:

- **Any telemetry, analytics or network logging.** Not optional, not opt-in, not
  anonymous. An earlier version of this app silently reported every download to a
  server; that is why this project exists in its current form.
- **Pinning a YouTube player client** (`--extractor-args
  youtube:player_client=…`). Forcing the android client makes YouTube serve only
  legacy muxed streams, whose best under 720p is really the 360p stream — so
  every 720p download silently comes out 360p.
- **Dropping the height cap from any fallback branch** of the format selector.
  Same bug, different disguise.
- **Bundling yt-dlp, ffmpeg or spotdl into the exe.** A bundled yt-dlp is frozen
  at build time, which is exactly the rot the runtime self-updater prevents.
- **Calling Tk from a worker thread.** It can block the worker inside Tcl and
  presents as the job queue dying silently after one job.

## Testing a change

There's no automated suite yet. What's worth doing by hand:

- Build a real AVI (`ffmpeg -f lavfi -i testsrc=duration=5 -f lavfi -i
  sine=duration=5 -c:v msmpeg4v3 -c:a pcm_s16le t.avi`) and run every Edit
  operation on it. Those codecs cannot be stream-copied into MP4, so they
  exercise the re-encode fallback.
- Queue a download, a Music item and a batch of edits together, then use Skip and
  Stop all.
- Check that a failing job reports `failed` and the queue carries on to the next.
