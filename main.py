
import time
import os
import sys
import subprocess
from urllib.parse import urlparse

import psutil  # pip install psutil

SPOTIFY_EXE = "Spotify.exe"
URL_FILE = r"C:\spotifylaunch\url.txt"

# How often to restart/replay (in seconds)
INTERVAL_SECONDS = 10*60*60  

# How long to wait for Spotify to start (in seconds)
SPOTIFY_START_TIMEOUT = 60

def extract_id(spotify_url: str) -> str:
    """
    Extract the last non-empty path segment from a Spotify URL.
    Example: https://open.spotify.com/playlist/37i9dQZF... -> 37i9dQZF...
    """
    parsed = urlparse(spotify_url)
    parts = [p for p in parsed.path.split("/") if p]
    if not parts:
        raise ValueError(f"Invalid Spotify URL: {spotify_url}")
    return parts[-1]


def create_spotify_uri(playlist_url: str, track_url: str) -> str:
    """
    Build a Spotify URI that starts a specific track within a playlist context.
    """
    playlist_id = extract_id(playlist_url)
    track_id = extract_id(track_url)
    return f"spotify:track:{track_id}?context=spotify%3Aplaylist%3A{playlist_id}"


def spotify_running() -> bool:
    """Return True if any Spotify.exe process is running."""
    for proc in psutil.process_iter(["name"]):
        try:
            if proc.info.get("name") == SPOTIFY_EXE:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def kill_spotify() -> None:
    """
    Kill all Spotify.exe processes if they are running.
    Use psutil first; fallback to taskkill /F for stubborn cases.
    """
    found = False
    for proc in psutil.process_iter(["name", "pid"]):
        try:
            if proc.info.get("name") == SPOTIFY_EXE:
                proc.kill()
                found = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if found:
        time.sleep(1.0)

    if spotify_running():
        try:
            subprocess.run(
                ["taskkill", "/IM", SPOTIFY_EXE, "/F"],
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception as e:
            FileNotFoundError(f"taskkill failed: {e}")

        time.sleep(0.5)


def read_urls(url_file: str) -> tuple[str, str]:
    """Read playlist and track URLs from file (line 1 = playlist, line 2 = track)."""
    if not os.path.isfile(url_file):
        raise FileNotFoundError(f"URL file not found: {url_file}")

    with open(url_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    if len(lines) < 2:
        raise ValueError("Text file must contain a playlist link on line 1 and a track link on line 2.")

    return lines[0], lines[1]


def start_spotify_with_uri(uri: str) -> None:
    """Start Spotify via OS shell association with the given URI."""
    try:
        os.startfile(uri)  # type: ignore[attr-defined]  # Windows-only
    except OSError as e:
        raise RuntimeError(f"Failed to start Spotify with URI: {e}") from e


def wait_for_spotify(timeout: int = SPOTIFY_START_TIMEOUT) -> None:
    """Wait for Spotify to be detected as running within timeout seconds."""
    deadline = time.time() + timeout
    while not spotify_running():
        if time.time() > deadline:
            raise TimeoutError("Spotify did not start within timeout.")
        time.sleep(1)


def run_cycle() -> None:
    """
    One full cycle:
      - kill Spotify
      - read URL file
      - start target track in playlist context
      - wait for running
    """
    kill_spotify()

    playlist_url, track_url = read_urls(URL_FILE)
    uri = create_spotify_uri(playlist_url, track_url)

    start_spotify_with_uri(uri)
    wait_for_spotify()


def main() -> None:
    try:
        # Run immediately once
        run_cycle()

        # Then repeat forever every INTERVAL_SECONDS
        while True:
            remaining = INTERVAL_SECONDS
            while remaining > 0:
                chunk = min(60, remaining)  # sleep up to 60s at a time
                time.sleep(chunk)
                remaining -= chunk
            # Run again
            run_cycle()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
