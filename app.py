"""
Local web server for the playlist/video downloader.

Run this instead of gui.py to get a rich browser-based UI at
http://127.0.0.1:5000 — it opens automatically in your default browser.
Wraps the same spotify_client, gaana_client, youtube_downloader, and
youtube_direct modules; downloads run on background threads and the page
polls for progress.

Protected by a simple login (APP_USERNAME / APP_PASSWORD in .env) so it's
safe to expose beyond localhost — e.g. over a private Tailscale network —
without being an open door to anyone who finds the address.
"""

import os
import secrets
import subprocess
import threading
import uuid
import webbrowser
from datetime import timedelta
from functools import wraps

from flask import Flask, jsonify, render_template, request, session, redirect, url_for
from dotenv import load_dotenv

from spotify_client import get_playlist_tracks as get_spotify_tracks
from gaana_client import get_playlist_tracks as get_gaana_tracks
from youtube_downloader import search_youtube, download_audio, sanitize_filename
from youtube_direct import list_formats, download_selected
from youtube_playlist import list_playlist_videos, download_playlist_video, estimate_video_size

load_dotenv()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
OUTPUT_DIR = "downloads"

APP_USERNAME = os.getenv("APP_USERNAME", "")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.permanent_session_lifetime = timedelta(days=14)

# In-memory job tracking: job_id -> {"log": [...], "done": bool, "total": int, "current": int}
jobs = {}
jobs_lock = threading.Lock()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        valid = bool(APP_PASSWORD) and secrets.compare_digest(username, APP_USERNAME) \
            and secrets.compare_digest(password, APP_PASSWORD)
        if valid:
            session.clear()
            session["logged_in"] = True
            session.permanent = True
            return redirect(request.args.get("next") or url_for("index"))
        error = "Incorrect username or password."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


def _new_job(total=0):
    job_id = uuid.uuid4().hex
    with jobs_lock:
        jobs[job_id] = {"log": [], "done": False, "total": total, "current": 0, "cancelled": False}
    return job_id


def _log(job_id, message):
    with jobs_lock:
        jobs[job_id]["log"].append(message)


def _set(job_id, **kwargs):
    with jobs_lock:
        jobs[job_id].update(kwargs)


@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/api/fetch", methods=["POST"])
@login_required
def api_fetch():
    data = request.get_json(force=True)
    source = data.get("source")
    url = (data.get("url") or "").strip()

    if not url:
        return jsonify({"error": "Please provide a link."}), 400

    try:
        if source == "spotify":
            tracks = get_spotify_tracks(url)
            return jsonify({"type": "playlist", "tracks": tracks})
        if source == "gaana":
            tracks = get_gaana_tracks(url)
            return jsonify({"type": "playlist", "tracks": tracks})
        if source == "youtube":
            info, video_formats, audio_formats = list_formats(url)
            return jsonify({
                "type": "youtube",
                "title": info.get("title", "Unknown"),
                "video_formats": video_formats,
                "audio_formats": audio_formats,
            })
        if source == "youtube_playlist":
            title, videos = list_playlist_videos(url)
            return jsonify({
                "type": "youtube_playlist",
                "title": title,
                "videos": videos,
            })
        return jsonify({"error": "Unknown source."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/download/playlist", methods=["POST"])
@login_required
def api_download_playlist():
    data = request.get_json(force=True)
    tracks = data.get("tracks") or []
    if not tracks:
        return jsonify({"error": "No tracks provided."}), 400
    if not YOUTUBE_API_KEY:
        return jsonify({"error": "Missing YOUTUBE_API_KEY — set it in your .env file."}), 400

    job_id = _new_job(total=len(tracks))
    threading.Thread(target=_run_playlist_download, args=(job_id, tracks), daemon=True).start()
    return jsonify({"job_id": job_id})


def _run_playlist_download(job_id, tracks):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    failed = skipped = 0
    total = len(tracks)

    for i, track in enumerate(tracks, 1):
        if jobs.get(job_id, {}).get("cancelled"):
            _log(job_id, f"Stopped by user after {i - 1}/{total} tracks.")
            _set(job_id, done=True)
            return

        safe_name = sanitize_filename(track)
        expected_path = os.path.join(OUTPUT_DIR, f"{safe_name}.mp3")

        if os.path.exists(expected_path):
            _log(job_id, f"[{i}/{total}] Already have: {track}")
            skipped += 1
            _set(job_id, current=i)
            continue

        _log(job_id, f"[{i}/{total}] Searching: {track}")
        try:
            video_url = search_youtube(track, YOUTUBE_API_KEY)
        except Exception as e:
            msg = str(e)
            if "quota" in msg.lower() or "rateLimitExceeded" in msg:
                _log(job_id, "  YouTube API daily quota reached. Stopping here for today.")
                _log(job_id, f"  Downloaded so far: {i - 1 - failed}, remaining: {total - i + 1}")
                _log(job_id, "  Quota resets at midnight Pacific Time — rerun later to pick up where you left off.")
            else:
                _log(job_id, f"  Search error: {e}")
            _set(job_id, current=i, done=True)
            return

        if not video_url:
            _log(job_id, "  No match found.")
            failed += 1
        else:
            try:
                download_audio(video_url, OUTPUT_DIR, safe_name)
                _log(job_id, "  Done.")
            except Exception as e:
                _log(job_id, f"  Failed: {e}")
                failed += 1

        _set(job_id, current=i)

    downloaded = total - failed - skipped
    _log(job_id, f"Finished. {downloaded} downloaded, {skipped} already had, {failed} failed.")
    _set(job_id, done=True)


@app.route("/api/download/youtube-playlist", methods=["POST"])
@login_required
def api_download_youtube_playlist():
    data = request.get_json(force=True)
    videos = data.get("videos") or []
    is_audio = bool(data.get("is_audio"))
    max_height = int(data.get("max_height") or 1080)

    if not videos:
        return jsonify({"error": "No videos provided."}), 400

    job_id = _new_job(total=len(videos))
    threading.Thread(
        target=_run_youtube_playlist_download,
        args=(job_id, videos, is_audio, max_height),
        daemon=True,
    ).start()
    return jsonify({"job_id": job_id})


def _run_youtube_playlist_download(job_id, videos, is_audio, max_height):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    failed = skipped = 0
    total = len(videos)
    ext = "mp3" if is_audio else "mp4"

    for i, video in enumerate(videos, 1):
        if jobs.get(job_id, {}).get("cancelled"):
            _log(job_id, f"Stopped by user after {i - 1}/{total} videos.")
            _set(job_id, done=True)
            return

        safe_name = sanitize_filename(video["title"])
        expected_path = os.path.join(OUTPUT_DIR, f"{safe_name}.{ext}")

        if os.path.exists(expected_path):
            _log(job_id, f"[{i}/{total}] Already have: {video['title']}")
            skipped += 1
        else:
            _log(job_id, f"[{i}/{total}] Downloading: {video['title']}")
            try:
                download_playlist_video(video["url"], OUTPUT_DIR, safe_name, is_audio, max_height)
                _log(job_id, "  Done.")
            except Exception as e:
                _log(job_id, f"  Failed: {e}")
                failed += 1

        _set(job_id, current=i)

    downloaded = total - failed - skipped
    _log(job_id, f"Finished. {downloaded} downloaded, {skipped} already had, {failed} failed.")
    _set(job_id, done=True)


@app.route("/api/estimate-size", methods=["POST"])
@login_required
def api_estimate_size():
    data = request.get_json(force=True)
    videos = data.get("videos") or []
    is_audio = bool(data.get("is_audio"))
    max_height = int(data.get("max_height") or 1080)

    if not videos:
        return jsonify({"error": "No videos provided."}), 400

    job_id = _new_job(total=len(videos))
    _set(job_id, size_bytes=0, unknown_count=0)
    threading.Thread(
        target=_run_estimate_size,
        args=(job_id, videos, is_audio, max_height),
        daemon=True,
    ).start()
    return jsonify({"job_id": job_id})


def _run_estimate_size(job_id, videos, is_audio, max_height):
    total_bytes = 0
    unknown = 0

    for i, video in enumerate(videos, 1):
        try:
            size = estimate_video_size(video["url"], is_audio, max_height)
        except Exception:
            size = None

        if size:
            total_bytes += size
        else:
            unknown += 1

        _set(job_id, current=i, size_bytes=total_bytes, unknown_count=unknown)

    _log(job_id, "Size scan complete.")
    _set(job_id, done=True)


@app.route("/api/download/youtube", methods=["POST"])
@login_required
def api_download_youtube():
    data = request.get_json(force=True)
    url = (data.get("url") or "").strip()
    format_id = data.get("format_id")
    is_audio = bool(data.get("is_audio"))
    has_audio = bool(data.get("has_audio", True))
    title = data.get("title") or "video"

    if not url or not format_id:
        return jsonify({"error": "Missing url or format_id."}), 400

    job_id = _new_job(total=1)
    threading.Thread(
        target=_run_youtube_download,
        args=(job_id, url, format_id, is_audio, has_audio, title),
        daemon=True,
    ).start()
    return jsonify({"job_id": job_id})


def _run_youtube_download(job_id, url, format_id, is_audio, has_audio, title):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_title = sanitize_filename(title)
    try:
        _log(job_id, f"Downloading: {safe_title}")
        download_selected(url, format_id, OUTPUT_DIR, safe_title, is_audio=is_audio, has_audio=has_audio)
        _log(job_id, "Done.")
    except Exception as e:
        _log(job_id, f"Failed: {e}")
    _set(job_id, current=1, done=True)


@app.route("/api/cancel/<job_id>", methods=["POST"])
@login_required
def api_cancel(job_id):
    if job_id not in jobs:
        return jsonify({"error": "Unknown job."}), 404
    _set(job_id, cancelled=True)
    return jsonify({"ok": True})


@app.route("/api/progress/<job_id>")
@login_required
def api_progress(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job."}), 404
    return jsonify(job)


@app.route("/api/open-folder", methods=["POST"])
@login_required
def api_open_folder():
    path = os.path.abspath(OUTPUT_DIR)
    os.makedirs(path, exist_ok=True)
    try:
        if os.name == "nt":
            os.startfile(path)  # noqa: S606 — local desktop convenience only
        elif os.uname().sysname == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    if not APP_PASSWORD:
        print(
            "WARNING: APP_USERNAME/APP_PASSWORD are not set in .env — "
            "the login page will reject every attempt. Set them before "
            "relying on this for anything beyond 127.0.0.1."
        )

    # 0.0.0.0 makes this reachable over your LAN or a private network like
    # Tailscale, not just from this machine. The login screen is what keeps
    # that safe — never run this bound to 0.0.0.0 without APP_PASSWORD set,
    # and never forward this port on your router to the public internet.
    host = "0.0.0.0" if APP_PASSWORD else "127.0.0.1"
    local_url = "http://127.0.0.1:5000"
    threading.Timer(1.0, lambda: webbrowser.open(local_url)).start()
    app.run(host=host, port=5000, debug=False)
