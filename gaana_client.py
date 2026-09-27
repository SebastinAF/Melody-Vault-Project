"""
Fetches track names + artists from a public Gaana playlist.

Uses the unofficial `gaanaclient` library, which talks to Gaana's own
(unofficial) endpoints directly — no login or API key needed. Works with
either a full Gaana playlist URL or a bare seokey.
"""

from gaana import GaanaClient


def get_playlist_tracks(playlist_url: str) -> list[str]:
    """
    Returns a list of "Track Name - Artist1, Artist2" strings for every
    track in the given Gaana playlist.
    """
    tracks = []
    with GaanaClient() as client:
        playlist = client.get_playlist(playlist_url)
        for song in playlist.tracks:
            tracks.append(f"{song.title} - {song.artists}")

    return tracks
