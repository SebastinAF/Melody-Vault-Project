import os
from dotenv import load_dotenv

from spotify_client import get_playlist_tracks as get_spotify_tracks
from gaana_client import get_playlist_tracks as get_gaana_tracks
from youtube_downloader import search_youtube, download_audio, sanitize_filename
from youtube_direct import list_formats, download_selected
from youtube_playlist import list_playlist_videos, download_playlist_video

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

OUTPUT_DIR = "downloads"


def run_youtube_playlist():
    playlist_url = input("Enter YouTube playlist URL: ").strip()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("\nFetching playlist contents...")
    title, videos = list_playlist_videos(playlist_url)
    print(f"Playlist: {title}")
    print(f"Found {len(videos)} videos.\n")

    kind = input("Download (v)ideo or (a)udio for all of them? ").strip().lower()
    is_audio = kind.startswith("a")

    max_height = 1080
    if not is_audio:
        raw = input("Max resolution (e.g. 1080, 720, 480) [1080]: ").strip()
        if raw.isdigit():
            max_height = int(raw)

    failed = []
    skipped = 0
    ext = "mp3" if is_audio else "mp4"
    for i, video in enumerate(videos, 1):
        safe_name = sanitize_filename(video["title"])
        expected_path = os.path.join(OUTPUT_DIR, f"{safe_name}.{ext}")

        if os.path.exists(expected_path):
            print(f"[{i}/{len(videos)}] Already downloaded, skipping: {video['title']}")
            skipped += 1
            continue

        print(f"[{i}/{len(videos)}] Downloading: {video['title']}")
        try:
            download_playlist_video(video["url"], OUTPUT_DIR, safe_name, is_audio, max_height)
            print("  Done.")
        except Exception as e:
            print(f"  Failed: {e}")
            failed.append(video["title"])

    downloaded = len(videos) - len(failed) - skipped
    print(f"\nFinished. {downloaded} newly downloaded, {skipped} already had, {len(failed)} failed.")
    if failed:
        print("Could not download:")
        for t in failed:
            print(f"  - {t}")


def run_youtube_direct():
    video_url = input("Enter YouTube video URL: ").strip()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("\nFetching available formats...")
    info, video_formats, audio_formats = list_formats(video_url)
    print(f"\nTitle: {info.get('title', 'Unknown')}\n")

    kind = input("Download (v)ideo or (a)udio? ").strip().lower()
    is_audio = kind.startswith("a")
    options = audio_formats if is_audio else video_formats

    if not options:
        print("No matching formats found for this video.")
        return

    print(f"\nAvailable {'audio' if is_audio else 'video'} options:")
    for idx, f in enumerate(options, 1):
        print(f"  {idx}) {f['label']}")

    while True:
        raw = input(f"\nEnter number (1-{len(options)}): ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            chosen = options[int(raw) - 1]
            break
        print("Invalid choice, try again.")

    safe_title = sanitize_filename(info.get("title", "video"))
    print(f"\nDownloading: {chosen['label']}")
    try:
        download_selected(
            video_url,
            chosen["format_id"],
            OUTPUT_DIR,
            safe_title,
            is_audio=is_audio,
            has_audio=chosen.get("has_audio", True),
        )
        print("Done.")
    except Exception as e:
        print(f"Failed: {e}")


def main():
    print("Choose a source:")
    print("  1) Spotify playlist")
    print("  2) Gaana playlist")
    print("  3) YouTube (single video)")
    print("  4) YouTube (whole playlist)")
    choice = input("Enter 1, 2, 3, or 4: ").strip()

    if choice == "3":
        run_youtube_direct()
        return

    if choice == "4":
        run_youtube_playlist()
        return

    if not YOUTUBE_API_KEY:
        print("Missing credentials. Copy .env.example to .env and fill in your YouTube API key.")
        return

    playlist_url = input("Enter playlist URL: ").strip()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("\nFetching tracks...")
    if choice == "2":
        tracks = get_gaana_tracks(playlist_url)
    else:
        tracks = get_spotify_tracks(playlist_url)
    print(f"Found {len(tracks)} tracks.\n")

    failed = []
    skipped = 0
    for i, track in enumerate(tracks, 1):
        safe_name = sanitize_filename(track)
        expected_path = os.path.join(OUTPUT_DIR, f"{safe_name}.mp3")

        if os.path.exists(expected_path):
            print(f"[{i}/{len(tracks)}] Already downloaded, skipping: {track}")
            skipped += 1
            continue

        print(f"[{i}/{len(tracks)}] Searching: {track}")
        try:
            video_url = search_youtube(track, YOUTUBE_API_KEY)
        except Exception as e:
            msg = str(e)
            if "quota" in msg.lower() or "rateLimitExceeded" in msg:
                print("  YouTube API daily quota reached. Stopping here for today.")
                print("  Quota resets at midnight Pacific Time — rerun this script later")
                print("  and it will skip everything already downloaded and continue.")
            else:
                print(f"  Search error: {e}")
            break

        if not video_url:
            print("  No match found, skipping.")
            failed.append(track)
            continue

        try:
            print(f"  Downloading: {video_url}")
            download_audio(video_url, OUTPUT_DIR, safe_name)
            print("  Done.")
        except Exception as e:
            print(f"  Failed: {e}")
            failed.append(track)

    downloaded = len(tracks) - len(failed) - skipped
    print(f"\nFinished. {downloaded} newly downloaded, {skipped} already had, {len(failed)} failed.")
    if failed:
        print("Could not download:")
        for t in failed:
            print(f"  - {t}")


if __name__ == "__main__":
    main()