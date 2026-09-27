"""
Lets the user paste a single YouTube video URL, pick a resolution/quality
(with an approximate file size shown for each), choose video or audio, and
downloads exactly that stream with yt-dlp.
"""

import yt_dlp


def _format_size(num_bytes):
    if not num_bytes:
        return "size unknown"
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def list_formats(url: str):
    """
    Returns (info, video_formats, audio_formats), each a list of dicts:
      {"format_id": ..., "label": "1080p - mp4 - 45.2 MB", "has_audio": bool}
    sorted best-quality first.
    """
    ydl_opts = {"quiet": True, "skip_download": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    video_formats = []
    audio_formats = []

    for f in info.get("formats", []):
        vcodec = f.get("vcodec")
        acodec = f.get("acodec")
        if vcodec in (None, "none") and acodec in (None, "none"):
            continue  # e.g. storyboard/thumbnail-only entries

        size = f.get("filesize") or f.get("filesize_approx")
        size_str = _format_size(size)
        ext = f.get("ext")

        if vcodec and vcodec != "none":
            height = f.get("height") or 0
            resolution = f"{height}p" if height else (f.get("resolution") or "?")
            video_formats.append({
                "format_id": f["format_id"],
                "label": f"{resolution} - {ext} - {size_str}",
                "height": height,
                "has_audio": acodec not in (None, "none"),
            })
        elif acodec and acodec != "none":
            abr = f.get("abr") or 0
            bitrate = f"{int(abr)}kbps" if abr else "?"
            audio_formats.append({
                "format_id": f["format_id"],
                "label": f"{bitrate} - {ext} - {size_str}",
                "abr": abr,
            })

    video_formats.sort(key=lambda x: x["height"], reverse=True)
    audio_formats.sort(key=lambda x: x["abr"], reverse=True)

    return info, video_formats, audio_formats


def download_selected(
    url: str,
    format_id: str,
    output_dir: str,
    filename: str,
    is_audio: bool,
    has_audio: bool = True,
) -> None:
    """Downloads exactly the chosen format (merging in audio for video-only streams)."""
    ydl_opts = {
        "outtmpl": f"{output_dir}/{filename}.%(ext)s",
        "quiet": True,
        "noprogress": True,
    }

    if is_audio:
        ydl_opts["format"] = format_id
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    else:
        ydl_opts["format"] = format_id if has_audio else f"{format_id}+bestaudio/best"
        ydl_opts["merge_output_format"] = "mp4"

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
