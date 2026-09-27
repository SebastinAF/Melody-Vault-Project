"""
Fetches track names + artists from a public Spotify playlist.

Uses the SpotifyScraper library, which reads Spotify's own public playlist
pages (the same data your browser sees) instead of the official Web API —
so no Spotify Developer app, API key, login, or Premium account is needed.
It only works on playlists that are set to Public.
"""

from spotify_scraper import SpotifyClient


def get_playlist_tracks(playlist_url: str, max_tracks: int = 100000) -> list[str]:
    """
    Returns a list of "Track Name - Artist1, Artist2" strings for every
    track in the given public Spotify playlist.
    """
    tracks = []
    with SpotifyClient() as client:
        playlist = client.get_playlist(playlist_url, max_tracks=max_tracks)

        for entry in playlist.tracks:
            # Some versions expose each entry as a wrapper with a .track
            # attribute; others expose the Track object directly.
            track = getattr(entry, "track", entry)
            if track is None:
                continue
            name = track.name
            artists = ", ".join(a.name for a in track.artists)
            tracks.append(f"{name} - {artists}")

    return tracks