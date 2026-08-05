# Distributing YT-Pro privately

This folder is for handing the app to people you know, without publishing
anything. The code stays in a private repo; only the exe and a small version
file go on a public URL, and that URL isn't listed or indexed anywhere.

## One-time setup

1. Make a folder somewhere outside the repo, e.g. `C:\dev\ytpro-dist`, and copy
   `vercel.json` from here into it.
2. Deploy it once to get the URL:

```bash
npx vercel --cwd C:\dev\ytpro-dist
```

Say yes to a new project, name it something unremarkable. Vercel gives you a URL
like `https://ytpro-dist.vercel.app`.

3. Put that URL's `latest.json` into `ytpro/__init__.py`:

```python
UPDATE_URL = "https://ytpro-dist.vercel.app/latest.json"
```

That's the only line that needs changing. The exe URL is derived from it.

## Every release after that

1. Bump `__version__` in `ytpro/__init__.py`.
2. Run `release.bat`. That builds the exe, hashes it, and writes
   `release\latest.json` and `release\SHA256SUMS.txt`.
3. Copy everything from `release\` into your dist folder and redeploy:

```bash
npx vercel --prod --cwd C:\dev\ytpro-dist
```

Anyone already running YT-Pro gets offered the update on their next launch, and
the download is rejected if its hash doesn't match `latest.json`.

## Handing it to someone the first time

Send them `https://ytpro-dist.vercel.app/YT-Pro.exe`. Tell them two things:

- **Windows will warn** that the publisher is unknown, because the exe isn't
  code-signed. They click "More info" then "Run anyway". This is normal for
  unsigned software and not a sign of a problem.
- **First launch downloads about 160 MB** (yt-dlp and ffmpeg) into
  `%APPDATA%\YT-Pro`. It only happens once. spotdl is another 46 MB, fetched
  only if they use the Music tab.

## Why not just use GitHub Releases?

Because the repo is private, and private release assets need an auth token to
download. A static file needs no token, no account, and reveals nothing about
who published it. If the repo ever goes public, set `GITHUB_REPO` instead of
`UPDATE_URL` and the app switches to reading GitHub's releases API — the code
already supports both.

## Keeping it unlisted

- Vercel projects are not indexed unless you link to them from somewhere public.
- Don't put the URL in a public repo, a public gist, or a Reddit post.
- Add `deploy/` and `release/` to `.gitignore` if you'd rather the URL never
  touch the repo at all — though `UPDATE_URL` in the source will contain it
  either way, which is fine while the repo is private.
