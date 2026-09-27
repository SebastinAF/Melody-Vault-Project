"""
Desktop GUI for the playlist/video downloader — classic bordered look,
light blue & gold theme. Wraps the existing spotify_client, gaana_client,
youtube_downloader, and youtube_direct modules; no new dependencies needed
since tkinter ships with Python.
"""

import os
import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox
from dotenv import load_dotenv

from spotify_client import get_playlist_tracks as get_spotify_tracks
from gaana_client import get_playlist_tracks as get_gaana_tracks
from youtube_downloader import search_youtube, download_audio, sanitize_filename
from youtube_direct import list_formats, download_selected

load_dotenv()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
OUTPUT_DIR = "downloads"

# ---- Theme ----
BG_LIGHT_BLUE = "#DCEEFB"
PANEL_BLUE = "#EAF6FF"
GOLD = "#D4AF37"
DARK_GOLD = "#B8860B"
NAVY_TEXT = "#1B3A5C"
WHITE = "#FFFFFF"

FONT_TITLE = ("Georgia", 18, "bold")
FONT_SUBTITLE = ("Georgia", 10, "italic")
FONT_LABEL = ("Georgia", 11)
FONT_BUTTON = ("Georgia", 11, "bold")


class DownloaderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Melody Vault — Playlist Downloader")
        self.geometry("740x600")
        self.configure(bg=BG_LIGHT_BLUE)
        self.resizable(False, False)

        self.log_queue = queue.Queue()
        self.current_tracks = []
        self.current_video_info = None
        self.current_formats = {}

        self._build_style()
        self._build_ui()
        self.after(100, self._poll_log_queue)

    # ---------------- styling ----------------

    def _build_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("TFrame", background=BG_LIGHT_BLUE)
        style.configure("Panel.TFrame", background=PANEL_BLUE, relief="ridge", borderwidth=2)
        style.configure("TLabel", background=BG_LIGHT_BLUE, foreground=NAVY_TEXT, font=FONT_LABEL)
        style.configure("Title.TLabel", background=BG_LIGHT_BLUE, foreground=DARK_GOLD, font=FONT_TITLE)
        style.configure("Subtitle.TLabel", background=BG_LIGHT_BLUE, foreground=NAVY_TEXT, font=FONT_SUBTITLE)
        style.configure("Panel.TLabel", background=PANEL_BLUE, foreground=NAVY_TEXT, font=FONT_LABEL)

        style.configure(
            "Gold.TButton",
            background=GOLD,
            foreground=NAVY_TEXT,
            font=FONT_BUTTON,
            borderwidth=2,
            relief="raised",
            padding=6,
        )
        style.map("Gold.TButton", background=[("active", DARK_GOLD)])

        style.configure("TRadiobutton", background=PANEL_BLUE, foreground=NAVY_TEXT, font=FONT_LABEL)
        style.configure("TEntry", fieldbackground=WHITE, foreground=NAVY_TEXT)
        style.configure(
            "Gold.Horizontal.TProgressbar",
            troughcolor=PANEL_BLUE,
            background=GOLD,
            bordercolor=DARK_GOLD,
            lightcolor=GOLD,
            darkcolor=DARK_GOLD,
        )

    # ---------------- layout ----------------

    def _build_ui(self):
        ttk.Label(self, text="Melody Vault", style="Title.TLabel").pack(pady=(16, 2))
        ttk.Label(
            self, text="Spotify  \u2022  Gaana  \u2022  YouTube — all in one place", style="Subtitle.TLabel"
        ).pack(pady=(0, 12))

        # Source selection
        source_frame = ttk.Frame(self, style="Panel.TFrame", padding=12)
        source_frame.pack(fill="x", padx=20, pady=6)

        self.source_var = tk.StringVar(value="spotify")
        ttk.Label(source_frame, text="Source:", style="Panel.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(
            source_frame, text="Spotify Playlist", variable=self.source_var, value="spotify",
            command=self._on_source_change,
        ).grid(row=0, column=1, padx=8)
        ttk.Radiobutton(
            source_frame, text="Gaana Playlist", variable=self.source_var, value="gaana",
            command=self._on_source_change,
        ).grid(row=0, column=2, padx=8)
        ttk.Radiobutton(
            source_frame, text="YouTube Video", variable=self.source_var, value="youtube",
            command=self._on_source_change,
        ).grid(row=0, column=3, padx=8)

        # URL entry
        url_frame = ttk.Frame(self, style="Panel.TFrame", padding=12)
        url_frame.pack(fill="x", padx=20, pady=6)
        ttk.Label(url_frame, text="Link:", style="Panel.TLabel").pack(side="left")
        self.url_entry = ttk.Entry(url_frame, width=52, font=FONT_LABEL)
        self.url_entry.pack(side="left", padx=8, fill="x", expand=True)
        self.fetch_button = ttk.Button(url_frame, text="Fetch", style="Gold.TButton", command=self._on_fetch)
        self.fetch_button.pack(side="left")

        # YouTube-only: video/audio + quality list (shown only for that source)
        self.yt_options_frame = ttk.Frame(self, style="Panel.TFrame", padding=12)
        self.kind_var = tk.StringVar(value="video")
        ttk.Label(self.yt_options_frame, text="Type:", style="Panel.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(
            self.yt_options_frame, text="Video", variable=self.kind_var, value="video",
            command=self._refresh_quality_list,
        ).grid(row=0, column=1)
        ttk.Radiobutton(
            self.yt_options_frame, text="Audio", variable=self.kind_var, value="audio",
            command=self._refresh_quality_list,
        ).grid(row=0, column=2)
        ttk.Label(self.yt_options_frame, text="Quality:", style="Panel.TLabel").grid(
            row=1, column=0, sticky="w", pady=(8, 0)
        )
        self.quality_listbox = tk.Listbox(
            self.yt_options_frame, height=5, width=52, bg=WHITE, fg=NAVY_TEXT,
            selectbackground=GOLD, selectforeground=NAVY_TEXT, font=FONT_LABEL,
            relief="sunken", borderwidth=2,
        )
        self.quality_listbox.grid(row=2, column=0, columnspan=3, pady=(4, 0), sticky="ew")

        # Track list (for Spotify/Gaana playlists)
        self.track_frame = ttk.Frame(self, style="Panel.TFrame", padding=12)
        self.track_listbox = tk.Listbox(
            self.track_frame, height=11, width=68, bg=WHITE, fg=NAVY_TEXT,
            selectbackground=GOLD, selectforeground=NAVY_TEXT, font=FONT_LABEL,
            relief="sunken", borderwidth=2,
        )
        scrollbar = ttk.Scrollbar(self.track_frame, orient="vertical", command=self.track_listbox.yview)
        self.track_listbox.configure(yscrollcommand=scrollbar.set)
        self.track_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Download action + progress bar
        action_frame = ttk.Frame(self, style="TFrame")
        action_frame.pack(fill="x", padx=20, pady=8)
        self.download_button = ttk.Button(
            action_frame, text="Download", style="Gold.TButton", command=self._on_download
        )
        self.download_button.pack(side="left")
        self.progress = ttk.Progressbar(
            action_frame, orient="horizontal", length=420, mode="determinate",
            style="Gold.Horizontal.TProgressbar",
        )
        self.progress.pack(side="left", padx=12, fill="x", expand=True)

        # Log area
        log_frame = ttk.Frame(self, style="Panel.TFrame", padding=8)
        log_frame.pack(fill="both", expand=True, padx=20, pady=(6, 16))
        self.log_text = tk.Text(
            log_frame, height=8, bg=WHITE, fg=NAVY_TEXT, font=("Consolas", 9),
            relief="sunken", borderwidth=2, state="disabled",
        )
        self.log_text.pack(fill="both", expand=True)

        self._on_source_change()

    def _on_source_change(self):
        if self.source_var.get() == "youtube":
            self.track_frame.pack_forget()
            self.yt_options_frame.pack(fill="x", padx=20, pady=6)
        else:
            self.yt_options_frame.pack_forget()
            self.track_frame.pack(fill="both", expand=True, padx=20, pady=6)

    # ---------------- logging ----------------

    def _log(self, message):
        self.log_queue.put(message)

    def _poll_log_queue(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get_nowait()
            self.log_text.configure(state="normal")
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.after(150, self._poll_log_queue)

    # ---------------- fetch ----------------

    def _on_fetch(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Missing link", "Please paste a link first.")
            return
        self.fetch_button.configure(state="disabled")
        threading.Thread(target=self._fetch_worker, args=(url,), daemon=True).start()

    def _fetch_worker(self, url):
        source = self.source_var.get()
        try:
            if source == "spotify":
                self._log("Fetching tracks from Spotify...")
                tracks = get_spotify_tracks(url)
                self.after(0, self._populate_tracks, tracks)
            elif source == "gaana":
                self._log("Fetching tracks from Gaana...")
                tracks = get_gaana_tracks(url)
                self.after(0, self._populate_tracks, tracks)
            else:  # youtube
                self._log("Fetching video info...")
                info, video_formats, audio_formats = list_formats(url)
                self.current_video_info = info
                self.current_formats = {"video": video_formats, "audio": audio_formats}
                self.after(0, self._refresh_quality_list)
                self._log(f"Loaded: {info.get('title', 'Unknown')}")
        except Exception as e:
            self._log(f"Error: {e}")
        finally:
            self.after(0, lambda: self.fetch_button.configure(state="normal"))

    def _populate_tracks(self, tracks):
        self.current_tracks = tracks
        self.track_listbox.delete(0, "end")
        for t in tracks:
            self.track_listbox.insert("end", t)
        self._log(f"Found {len(tracks)} tracks.")

    def _refresh_quality_list(self):
        kind = self.kind_var.get()
        options = self.current_formats.get(kind, [])
        self.quality_listbox.delete(0, "end")
        for f in options:
            self.quality_listbox.insert("end", f["label"])

    # ---------------- download ----------------

    def _on_download(self):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        source = self.source_var.get()

        if source == "youtube":
            sel = self.quality_listbox.curselection()
            if not sel or not self.current_video_info:
                messagebox.showwarning("No quality selected", "Fetch a video and pick a quality first.")
                return
            kind = self.kind_var.get()
            chosen = self.current_formats[kind][sel[0]]
            self.download_button.configure(state="disabled")
            threading.Thread(
                target=self._download_youtube_worker, args=(chosen, kind == "audio"), daemon=True
            ).start()
        else:
            if not self.current_tracks:
                messagebox.showwarning("No tracks", "Fetch a playlist first.")
                return
            if not YOUTUBE_API_KEY:
                messagebox.showerror("Missing API key", "Set YOUTUBE_API_KEY in your .env file first.")
                return
            self.download_button.configure(state="disabled")
            threading.Thread(target=self._download_playlist_worker, daemon=True).start()

    def _download_youtube_worker(self, chosen, is_audio):
        url = self.url_entry.get().strip()
        title = sanitize_filename(self.current_video_info.get("title", "video"))
        try:
            self._log(f"Downloading: {chosen['label']}")
            download_selected(
                url, chosen["format_id"], OUTPUT_DIR, title,
                is_audio=is_audio, has_audio=chosen.get("has_audio", True),
            )
            self._log("Done.")
        except Exception as e:
            self._log(f"Failed: {e}")
        finally:
            self.after(0, lambda: self.download_button.configure(state="normal"))

    def _download_playlist_worker(self):
        tracks = self.current_tracks
        total = len(tracks)
        self.after(0, lambda: self.progress.configure(maximum=total, value=0))

        failed = skipped = 0
        for i, track in enumerate(tracks, 1):
            safe_name = sanitize_filename(track)
            expected_path = os.path.join(OUTPUT_DIR, f"{safe_name}.mp3")

            if os.path.exists(expected_path):
                self._log(f"[{i}/{total}] Already have: {track}")
                skipped += 1
            else:
                self._log(f"[{i}/{total}] Searching: {track}")
                video_url = search_youtube(track, YOUTUBE_API_KEY)
                if not video_url:
                    self._log("  No match found.")
                    failed += 1
                else:
                    try:
                        download_audio(video_url, OUTPUT_DIR, safe_name)
                        self._log("  Done.")
                    except Exception as e:
                        self._log(f"  Failed: {e}")
                        failed += 1

            self.after(0, lambda v=i: self.progress.configure(value=v))

        downloaded = total - failed - skipped
        self._log(f"Finished. {downloaded} downloaded, {skipped} already had, {failed} failed.")
        self.after(0, lambda: self.download_button.configure(state="normal"))


if __name__ == "__main__":
    app = DownloaderApp()
    app.mainloop()
