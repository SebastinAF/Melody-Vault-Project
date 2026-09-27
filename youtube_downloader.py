"""
Searches YouTube (via the official YouTube Data API v3) for a best-match video
for each track query, then downloads the audio with yt-dlp.

Note: yt-dlp does the actual download — the YouTube Data API is only used for
search, since the Data API itself has no download endpoint.
"""

import os
from googleapiclient.discovery import build
import yt_dlp


def search_youtube(query: str, api_key: str) -> str | None:
    """Returns the URL of the top YouTube video result for the query, or None."""
    youtube = build("youtube", "v3", developerKey=api_key)
    request = youtube.search().list(
        q=f"{query} audio",
        part="snippet",
        maxResults=1,
        type="video",
    )
    response = request.execute()
    items = response.get("items", [])
    if not items:
        return None
    video_id = items[0]["id"]["videoId"]
    return f"https://www.youtube.com/watch?v={video_id}"


def download_audio(url: str, output_dir: str, filename: str) -> None:
    """Downloads the audio track of a YouTube video as an mp3 into output_dir."""
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(output_dir, f"{filename}.%(ext)s"),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "256",
            }
        ],
        "quiet": True,
        "noprogress": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def sanitize_filename(name: str) -> str:
    """Strips characters that aren't safe in file names."""
    return "".join(c for c in name if c not in '\\/:*?"<>|').strip()
