# Security

## Verifying your download

Every release lists the exe's SHA-256 in the release notes and in
`SHA256SUMS.txt`. Check it before running:

```powershell
Get-FileHash .\YT-Pro.exe -Algorithm SHA256
```

If that doesn't match the published value, don't run it. **Releases on this
repository are the only official source** — anything downloaded elsewhere isn't
something I can vouch for.

## The Windows warning is expected

The exe isn't code-signed, so SmartScreen will say the publisher is unknown.
Click **More info → Run anyway**. This is normal for unsigned software and not a
sign of a problem; a signing certificate costs a few hundred dollars a year and
this project doesn't have a budget.

Antivirus false positives are also common with PyInstaller-built exes — several
engines flag the bootloader itself, regardless of what the program does. That's
part of why the source is here: you can read it, and you can build your own copy
with `build.bat`.

## What the app does on the network

Worth being precise, since you're running an unsigned binary:

- **Downloads yt-dlp and ffmpeg on first launch** (and spotdl the first time you
  use the Music tab) into `%APPDATA%\YT-Pro`, from the official
  `github.com/yt-dlp`, `github.com/BtbN/FFmpeg-Builds` and
  `github.com/spotDL` releases.
- **Runs `yt-dlp -U` once a day** to keep it current, and checks this repo's
  latest release to see if the app itself is newer.
- **Fetches whatever you paste in**, via those tools.

That's the complete list. There is **no telemetry, no analytics, and no usage
reporting of any kind** — nothing about what you download leaves your machine.
Your settings live in `%USERPROFILE%\.ytpro_config.json` and stay local.

If you want to confirm rather than take my word for it, `ytpro/tools.py` holds
every URL the app knows about.

## Reporting a vulnerability

Open a **private security advisory** through the Security tab of this repository
rather than a public issue. That way it can be fixed before it's public.

Please do report:

- Anything that lets a downloaded file or a pasted link execute code
- A way to make the self-updater install something that isn't the published
  release
- Command injection through a filename or URL

## Known limitations

- **The exe is unsigned**, so it cannot prove its own origin. The SHA-256 is the
  substitute.
- **Updates are verified by checksum only** when a checksum is published for
  them; the GitHub release route trusts TLS and GitHub. There's no signature
  chain.
- **The bundled tools are trusted implicitly** once downloaded over HTTPS from
  their official release URLs.
