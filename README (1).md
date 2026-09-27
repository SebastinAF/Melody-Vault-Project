# Melody Vault — Playlist / Video Downloader

A personal, local tool for pulling music and video onto your own machine
from a playlist link (Spotify, Gaana, or YouTube) or a direct YouTube
link — in whichever interface you prefer: terminal, desktop app, or a
rich local web page.

---

## Contents

1. [What it does](#1-what-it-does)
2. [Project structure](#2-project-structure)
3. [Requirements](#3-requirements)
4. [Installation](#4-installation)
5. [Configuration](#5-configuration)
6. [Running it](#6-running-it)
   - [Terminal (`main.py`)](#terminal-mainpy)
   - [Desktop GUI (`gui.py`)](#desktop-gui-guipy)
   - [Web UI (`app.py`)](#web-ui-apppy)
7. [The four modes, explained](#7-the-four-modes-explained)
8. [Module reference](#8-module-reference)
9. [Web API reference](#9-web-api-reference)
10. [Troubleshooting](#10-troubleshooting)
11. [Limits & legal notes](#11-limits--legal-notes)
12. [Private remote access (Tailscale)](#12-private-remote-access-tailscale)

---

## 1. What it does

Four ways to get media into your `downloads/` folder:

| Mode | Input | What happens |
|---|---|---|
| **Spotify playlist** | Public Spotify playlist link | Reads the track list, finds each song on YouTube, downloads audio |
| **Gaana playlist** | Public Gaana playlist link | Same idea, via Gaana |
| **YouTube video** | A single video link | Lists every resolution/bitrate with file size, downloads the one you pick |
| **YouTube playlist** | A YouTube playlist link | Lists every video, estimates total download size, downloads them all at your chosen quality |

Three ways to use it — all built on the same underlying modules:

- **`main.py`** — plain terminal prompts
- **`gui.py`** — a desktop window (Tkinter), light-blue & gold themed
- **`app.py`** — a rich local web page at `http://127.0.0.1:5000`, same theme, live progress bar and activity log

---

## 2. Project structure

```
Music download/
├── main.py                 ← terminal entry point
├── gui.py                  ← desktop GUI entry point
├── app.py                  ← Flask web server entry point
│
├── spotify_client.py       ← reads a public Spotify playlist's tracks
├── gaana_client.py         ← reads a public Gaana playlist's tracks
├── youtube_downloader.py   ← searches YouTube + downloads matched audio
├── youtube_direct.py       ← single YouTube video: list formats, download one
├── youtube_playlist.py     ← full YouTube playlist: list videos, estimate size, bulk download
│
├── templates/
│   └── index.html          ← web UI page structure
├── static/
│   ├── style.css           ← light-blue & gold styling
│   └── script.js           ← web UI behavior (tabs, fetch, download, progress polling)
│
├── requirements.txt
├── .env.example             ← copy to .env and fill in your YouTube API key
├── .env                      ← your actual key (not shared/committed)
└── downloads/                ← everything ends up here
```

---

## 3. Requirements

- **Python 3.10+**
- **ffmpeg** on your system PATH (used to extract/merge audio and video)
  - Windows: `winget install ffmpeg` (restart your terminal after)
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`
- A **YouTube Data API v3 key** (free) — needed only for the two playlist-matching modes (Spotify/Gaana), not for the direct YouTube modes

No Spotify or Gaana account, API key, or login is required for any of it.

---

## 4. Installation

```bash
python -m venv venv
# Windows:
.\venv\Scripts\Activate.ps1
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

`requirements.txt` covers everything: `spotifyscraper`, `gaanaclient`,
`google-api-python-client`, `yt-dlp`, `python-dotenv`, and `flask` (for
the web UI).

---

## 5. Configuration

Get a YouTube API key:

1. Go to https://console.cloud.google.com/
2. Create a project → enable **YouTube Data API v3**
3. Create Credentials → **API key** → choose **Public data** (not "User data") when asked, since this only does anonymous searches

Then:

```bash
cp .env.example .env
```

Open `.env` and paste your key:

```
YOUTUBE_API_KEY=your_key_here
```

That's the only credential the whole project needs.

---

## 6. Running it

### Terminal (`main.py`)

```bash
python main.py
```

```
Choose a source:
  1) Spotify playlist
  2) Gaana playlist
  3) YouTube (single video)
  4) YouTube (whole playlist)
Enter 1, 2, 3, or 4:
```

Follow the prompts for whichever mode you picked (see [section 7](#7-the-four-modes-explained)).

### Desktop GUI (`gui.py`)

```bash
python gui.py
```

Opens a light-blue & gold desktop window with source radio buttons, a
link field, a track/video list, quality picker, progress bar, and a log
panel. No extra install — uses `tkinter`, which ships with Python.

### Web UI (`app.py`)

```bash
python app.py
```

Opens `http://127.0.0.1:5000` in your default browser automatically.
Runs entirely on your machine — nothing leaves `127.0.0.1`. Same four
source tabs, with glassmorphism cards, an animated gold progress bar, and
a live terminal-style activity console. A button jumps straight to the
`downloads/` folder when a run finishes.

---

## 7. The four modes, explained

### Spotify playlist / Gaana playlist

1. Paste a **public** playlist link (private playlists aren't readable —
   this project never logs into either service).
2. The track list (title + artist) is read directly from each platform's
   own public pages via two unofficial libraries — `spotifyscraper` and
   `gaanaclient` — no API key or login needed for this step.
3. For each track, `youtube_downloader.py` searches YouTube (via the
   YouTube Data API) for the closest match and downloads its audio as mp3.
4. Tracks already present in `downloads/` are automatically skipped —
   safe to rerun the same playlist link later (e.g. after hitting a daily
   quota limit) and it'll pick up where it left off.

### YouTube video (single)

1. Paste one video link.
2. `youtube_direct.py` lists every available resolution (or audio
   bitrate) with an approximate file size, pulled straight from YouTube
   via `yt-dlp` — no API key needed for this mode.
3. Choose **video** or **audio**, pick a quality, and it downloads
   exactly that stream (merging in the best audio track automatically for
   high-res video-only formats).
4. If you accidentally paste a playlist link here, it errors clearly
   instead of silently doing nothing.

### YouTube playlist (whole)

1. Paste a playlist link.
2. `youtube_playlist.py` lists every video's title quickly (without
   resolving full format data per video, to keep it fast).
3. Choose **video** (with a max-resolution ceiling, 360p–4K) or **audio**.
4. A background size scan then estimates the total download size,
   updating live (`Scanning… ~1.2 GB so far (3/7)`) since getting real
   sizes requires resolving each video individually.
5. Download All fetches every video in the playlist at your chosen
   quality, skipping anything already downloaded.

---

## 8. Module reference

| File | Purpose |
|---|---|
| `spotify_client.py` | `get_playlist_tracks(url)` → list of `"Title - Artist"` strings, via SpotifyScraper |
| `gaana_client.py` | `get_playlist_tracks(url)` → same shape, via gaanaclient |
| `youtube_downloader.py` | `search_youtube(query, api_key)` finds a video; `download_audio(url, dir, name)` downloads it as mp3; `sanitize_filename()` strips unsafe characters |
| `youtube_direct.py` | `list_formats(url)` → (info, video_formats, audio_formats) with sizes; `download_selected(...)` downloads one chosen format |
| `youtube_playlist.py` | `list_playlist_videos(url)` → title + video list; `estimate_video_size(...)` / bulk size scanning; `download_playlist_video(...)` downloads one video at a quality ceiling |

Each of these is interface-agnostic — `main.py`, `gui.py`, and `app.py`
all call the exact same functions, just with different front ends wrapped
around them.

---

## 9. Web API reference

For the Flask server (`app.py`), used internally by `static/script.js`:

| Endpoint | Method | Body | Returns |
|---|---|---|---|
| `/api/fetch` | POST | `{source, url}` | Track list or video/playlist info depending on source |
| `/api/download/playlist` | POST | `{tracks}` | `{job_id}` |
| `/api/download/youtube` | POST | `{url, format_id, is_audio, has_audio, title}` | `{job_id}` |
| `/api/download/youtube-playlist` | POST | `{videos, is_audio, max_height}` | `{job_id}` |
| `/api/estimate-size` | POST | `{videos, is_audio, max_height}` | `{job_id}` |
| `/api/progress/<job_id>` | GET | — | `{log, done, total, current, size_bytes?, unknown_count?}` |
| `/api/open-folder` | POST | — | Opens `downloads/` in your file explorer |

Jobs run on background threads and are tracked in an in-memory `jobs`
dict keyed by a UUID; the frontend polls `/api/progress/<job_id>` every
~1 second until `done: true`.

---

## 10. Troubleshooting

**`ModuleNotFoundError` after adding a new file** — you updated
`requirements.txt` but haven't installed yet: run
`pip install -r requirements.txt` again (or `pip install <package>`
directly to confirm it installs cleanly).

**`quota exceeded` / `rateLimitExceeded` error** — the YouTube Data
API's free tier is 10,000 units/day; a search costs 100 units (~100
searches/day). Both `main.py` and `app.py` catch this, log a clear
message, and stop cleanly rather than crashing — rerun after it resets
at **midnight Pacific Time**; already-downloaded tracks are skipped
automatically.

**Pasted a playlist link into the "single video" option** — it now
detects this and shows a clear error asking for a single video link (or
use the "YouTube playlist" mode instead).

**"An environment file is configured but terminal environment injection
is disabled" (VS Code notice)** — safe to ignore/dismiss. The script
loads `.env` itself via `python-dotenv`; it doesn't rely on VS Code's
terminal injection.

**Downloads stall or fail on a huge file** — check disk space first;
high-resolution long videos can be several GB, and the merge step
briefly needs space for the separate video + audio parts plus the final
file. Interrupted downloads resume automatically via `yt-dlp`'s `.part`
file handling on rerun.

---

## 11. Limits & legal notes

- Both Spotify and Gaana playlists must be **public**.
- `spotifyscraper` and `gaanaclient` are unofficial, community-maintained
  libraries reading each platform's own public web pages rather than a
  registered API — if either site changes its structure, update with
  `pip install -U spotifyscraper` / `pip install -U gaanaclient`.
- Spotify/Gaana track matching against YouTube is approximate — it takes
  the top search hit for `"<track> <artist> audio"`, which is usually
  correct but not guaranteed.
- The YouTube Data API's free quota is 10,000 units/day, only used by
  the two matching modes (Spotify/Gaana) — the direct YouTube modes
  don't touch it at all.
- **Copyright**: most songs and many videos on YouTube are copyrighted.
  Downloading them is against YouTube's Terms of Service and may be
  against copyright law depending on your country and use. This project
  is meant for personal backups of content you have the rights to, or
  content you're permitted to download (Creative Commons, your own
  uploads, royalty-free tracks) — not for redistributing copyrighted
  material. It does **not** attempt to circumvent Spotify's own DRM-
  protected audio; matched tracks come from YouTube, not from Spotify's
  streams directly.

---

## 12. Private remote access (Tailscale)

The web UI is now protected by a login screen, so it's safe to reach from
your phone or another device without exposing it to the public internet.
**Never** forward this app's port on your router — the recommended way to
reach it remotely is a private mesh network like [Tailscale](https://tailscale.com),
which connects only your own devices to each other, with nothing public.

### One-time setup

1. Install Tailscale on the machine that runs `app.py` (the one you've
   been using), and sign in: https://tailscale.com/download
2. Install Tailscale on your phone (or laptop) too, and sign in with the
   **same account**.
3. Set real credentials in `.env`:
   ```
   APP_USERNAME=your_chosen_username
   APP_PASSWORD=a_real_password
   SECRET_KEY=<paste output of: python -c "import secrets; print(secrets.token_hex(32))">
   ```
   Without `APP_PASSWORD` set, the server refuses to bind beyond
   `127.0.0.1` — this is a deliberate safety check in `app.py`.

### Running it

```bash
python app.py
```

Because `APP_PASSWORD` is now set, it binds to `0.0.0.0` — reachable from
any device on your Tailscale network. Find your machine's Tailscale
address either from the Tailscale app/admin console, or:

```bash
tailscale ip -4
```

Then from your phone (with Tailscale connected), visit:

```
http://<that-tailscale-ip>:5000
```

You'll land on the login screen first — sign in with the username and
password you set in `.env`. From there it behaves exactly like the local
version, just reachable from wherever you are.

### Keeping it running

The server only runs while `python app.py` is active in a terminal. For
it to be reachable whenever you want, on Windows the simplest option is
Task Scheduler (run `python app.py` at login, no window); on
macOS/Linux, a small `systemd` service or `pm2` (via `pm2 start app.py
--interpreter python3`) keeps it alive in the background and restarts it
if it crashes.

### Staying safe

- Keep `APP_PASSWORD` a real, non-guessable password — it's the only
  thing standing between your `downloads/` folder and anyone who joins
  your Tailscale network.
- Set a fixed `SECRET_KEY` (not blank) so you're not logged out every
  time the server restarts.
- Still never port-forward this app publicly — Tailscale is what makes
  "reachable from your phone" not mean "reachable by anyone."
