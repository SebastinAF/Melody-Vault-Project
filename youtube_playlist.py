"""
Handles a full YouTube playlist link: lists every video in it (fast, via
extract_flat so it doesn't resolve full format info per video), then can
download all of them at a chosen quality ceiling (video or audio).

Size estimation is a separate, slower step — it has to resolve each
video's real format list individually (same as the single-video mode),
so it's meant to be run as a background job with progress reporting.
"""

import yt_dlp


def list_playlist_videos(url: str):
    """
    Returns (playlist_title, videos), where videos is a list of dicts:
      {"id": ..., "title": ..., "url": "https://www.youtube.com/watch?v=..."}
    """
    ydl_opts = {"quiet": True, "extract_flat": "in_playlist", "skip_download": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if "entries" not in info:
        raise ValueError("That doesn't look like a playlist link.")

    videos = []
    for entry in info["entries"]:
        if not entry:
            continue  # deleted/private videos show up as None
        video_id = entry.get("id")
        videos.append({
            "id": video_id,
            "title": entry.get("title") or "Untitled",
            "url": f"https://www.youtube.com/watch?v={video_id}",
        })

    return info.get("title") or "Playlist", videos


def _pick_best_video_format(formats, max_height):
    candidates = [
        f for f in formats
        if f.get("vcodec") not in (None, "none") and (f.get("height") or 0) <= max_height
    ]
    if not candidates:
        candidates = [f for f in formats if f.get("vcodec") not in (None, "none")]
    if not candidates:
        return None
    return max(candidates, key=lambda f: f.get("height") or 0)


def _pick_best_audio_format(formats):
    candidates = [
        f for f in formats
        if f.get("acodec") not in (None, "none") and f.get("vcodec") in (None, "none")
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda f: f.get("abr") or 0)


def estimate_video_size(url: str, is_audio: bool, max_height: int = 1080):
    """
    Returns an estimated download size in bytes for one video at the given
    quality (video's chosen resolution + its matching audio track, or just
    the best audio track for audio downloads), or None if YouTube doesn't
    report a size for the relevant formats.
    """
    ydl_opts = {"quiet": True, "skip_download": True, "noplaylist": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    formats = info.get("formats", [])

    if is_audio:
        best = _pick_best_audio_format(formats)
        if not best:
            return None
        return best.get("filesize") or best.get("filesize_approx")

    video_fmt = _pick_best_video_format(formats, max_height)
    if not video_fmt:
        return None

    total = video_fmt.get("filesize") or video_fmt.get("filesize_approx") or 0
    got_size = bool(total)

    # High-res formats are usually video-only on YouTube, so a separate
    # audio track gets merged in — count its size too.
    if video_fmt.get("acodec") in (None, "none"):
        audio_fmt = _pick_best_audio_format(formats)
        if audio_fmt:
            a_size = audio_fmt.get("filesize") or audio_fmt.get("filesize_approx")
            if a_size:
                total += a_size
                got_size = True

    return total if got_size else None


def download_playlist_video(
    video_url: str,
    output_dir: str,
    filename: str,
    is_audio: bool,
    max_height: int = 1080,
) -> None:
    """Downloads one playlist video, capped at max_height for video downloads."""
    ydl_opts = {
        "outtmpl": f"{output_dir}/{filename}.%(ext)s",
        "noplaylist": True,
        "quiet": True,
        "noprogress": True,
    }

    if is_audio:
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    else:
        ydl_opts["format"] = f"bestvideo[height<={max_height}]+bestaudio/best[height<={max_height}]"
        ydl_opts["merge_output_format"] = "mp4"

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])