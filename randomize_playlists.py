#!/usr/bin/env python3
"""
Spotify Playlist Randomizer
Randomizes the order of tracks in all your playlists.
"""

import argparse
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import random
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Spotify credentials
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")

# Required scopes
SCOPES = [
    "playlist-read-private",      # Read private playlists
    "playlist-read-collaborative", # Read collaborative playlists
    "playlist-modify-public",     # Modify public playlists
    "playlist-modify-private",    # Modify private playlists
]


def create_spotify_client(headless=False):
    """Create authenticated Spotify client.

    In headless mode (cron/automation) never fall back to interactive OAuth.
    Nobody is there to complete a browser login, and spotipy's local callback
    server would block forever holding the redirect port — which also breaks
    every later run with "Address already in use".
    """
    if not CLIENT_ID or not CLIENT_SECRET:
        print("❌ Missing Spotify credentials in .env file")
        raise SystemExit(1)

    auth_manager = SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=" ".join(SCOPES),
        cache_path=".spotify_cache",
        open_browser=not headless,
    )

    if headless:
        # Refreshes via the cached refresh token; None means re-auth is required.
        token = auth_manager.validate_token(auth_manager.cache_handler.get_cached_token())
        if not token:
            print("❌ Spotify credentials expired — interactive re-auth required.")
            print("   --no-confirm cannot complete a browser login, so stopping here.")
            print("   Fix it by running once, interactively:")
            print("     cd %s" % os.path.dirname(os.path.abspath(__file__)))
            print("     .venv/bin/python randomize_playlists.py")
            raise SystemExit(1)

    return spotipy.Spotify(auth_manager=auth_manager)


def get_all_playlists(sp):
    """Get all playlists owned by the current user."""
    print("\n📚 Fetching your playlists...")
    playlists = []
    offset = 0
    limit = 50

    while True:
        results = sp.current_user_playlists(limit=limit, offset=offset)
        
        if not results["items"]:
            break

        for playlist in results["items"]:
            # Only include playlists owned by the user
            if playlist["owner"]["id"] == sp.current_user()["id"]:
                playlists.append({
                    "id": playlist["id"],
                    "name": playlist["name"],
                    "tracks_total": playlist["tracks"]["total"],
                    "public": playlist["public"],
                    "collaborative": playlist["collaborative"],
                })

        offset += limit
        if offset >= results["total"]:
            break

    print(f"✅ Found {len(playlists)} playlists you own")
    return playlists


def get_playlist_tracks(sp, playlist_id):
    """
    Get all track URIs from a playlist.
    Returns list of track URIs (spotify:track:...)
    Filters out invalid URIs (local files, podcasts, unavailable tracks, etc.)
    """
    tracks = []
    offset = 0
    limit = 100

    while True:
        results = sp.playlist_items(
            playlist_id,
            limit=limit,
            offset=offset,
            fields="items(track(uri,is_local)),next"
        )
        
        if not results["items"]:
            break

        for item in results["items"]:
            track = item.get("track")
            
            # Skip if track is None (deleted/unavailable)
            if not track:
                continue
            
            # Skip local files (they don't have valid URIs for API operations)
            if track.get("is_local"):
                continue
            
            uri = track.get("uri")
            
            # Only include valid Spotify track URIs
            # Format: spotify:track:xxxxxxxxxxxxxxxxxxxxx
            if uri and uri.startswith("spotify:track:"):
                tracks.append(uri)

        offset += limit
        if not results.get("next"):
            break

    return tracks


def randomize_playlist(sp, playlist_id, playlist_name):
    """
    Randomize the order of tracks in a playlist.
    
    IMPORTANT: This only shuffles tracks within the specified playlist.
    Tracks remain in their original playlist and are never mixed across playlists.
    
    Returns (success: bool, message: str)
    """
    try:
        # Get all tracks from THIS specific playlist only
        tracks = get_playlist_tracks(sp, playlist_id)
        
        if len(tracks) == 0:
            return False, "No valid tracks found (may contain only local files or unavailable tracks)"
        
        if len(tracks) < 2:
            return False, "Playlist has less than 2 valid tracks, skipping"
        
        # Shuffle the tracks (only tracks from this playlist)
        shuffled = tracks.copy()
        random.shuffle(shuffled)
        
        # Validate all URIs before sending to API
        valid_uris = [uri for uri in shuffled if uri and uri.startswith("spotify:track:")]
        
        if len(valid_uris) != len(shuffled):
            return False, f"Found {len(shuffled) - len(valid_uris)} invalid track URIs"
        
        # Replace tracks in the SAME playlist with shuffled order
        # Spotify API allows replacing up to 100 tracks at a time
        try:
            if len(shuffled) <= 100:
                # Replace all tracks at once in the same playlist
                sp.playlist_replace_items(playlist_id, shuffled)
            else:
                # For playlists with >100 tracks, replace in chunks
                # First, clear the playlist
                sp.playlist_replace_items(playlist_id, [])
                
                # Then add tracks back in batches of 100 (all to the same playlist)
                for i in range(0, len(shuffled), 100):
                    batch = shuffled[i:i + 100]
                    # Validate batch before sending
                    valid_batch = [uri for uri in batch if uri and uri.startswith("spotify:track:")]
                    if valid_batch:
                        sp.playlist_add_items(playlist_id, valid_batch)
            
            return True, f"Randomized {len(tracks)} tracks"
        
        except Exception as api_error:
            # Provide more helpful error message
            error_msg = str(api_error)
            if "Unsupported URL / URI" in error_msg or "400" in error_msg:
                return False, f"Invalid track URIs found (may contain local files or unavailable tracks)"
            return False, f"API Error: {error_msg}"
    
    except Exception as e:
        return False, f"Error: {str(e)}"


def run_randomize(playlists, sp, excluded_indices=None):
    """Randomize playlists and return (successful, failed, skipped) counts."""
    excluded_indices = excluded_indices or set()
    successful = 0
    failed = 0
    skipped = 0

    for i, playlist in enumerate(playlists):
        if i in excluded_indices:
            print(f"⏭️  Skipping: {playlist['name']}")
            skipped += 1
            continue

        print(f"🔄 Randomizing: {playlist['name']}...", end=" ")
        success, message = randomize_playlist(sp, playlist["id"], playlist["name"])

        if success:
            print(f"✅ {message}")
            successful += 1
        else:
            print(f"❌ {message}")
            failed += 1

        time.sleep(0.2)

    return successful, failed, skipped


def main():
    parser = argparse.ArgumentParser(description="Randomize Spotify playlists")
    parser.add_argument("--no-confirm", action="store_true",
                        help="Skip confirmation prompts (for cron/automation)")
    args = parser.parse_args()

    print("=" * 60)
    print("🔀 Spotify Playlist Randomizer")
    print("=" * 60)

    # Create Spotify client
    sp = create_spotify_client(headless=args.no_confirm)
    user = sp.current_user()
    print(f"\n👋 Hello, {user['display_name']}!")

    # Get all playlists
    playlists = get_all_playlists(sp)

    if not playlists:
        print("\n⚠️  You don't own any playlists to randomize!")
        return

    # Show playlists
    print("\n📋 Your playlists:")
    for i, playlist in enumerate(playlists, 1):
        privacy = "Public" if playlist["public"] else "Private"
        collab = " (Collaborative)" if playlist["collaborative"] else ""
        print(f"   {i}. {playlist['name']} - {playlist['tracks_total']} tracks [{privacy}]{collab}")

    if args.no_confirm:
        # Non-interactive mode: randomize all playlists
        print(f"\n🔀 Randomizing all {len(playlists)} playlists (--no-confirm)...\n")
        successful, failed, skipped = run_randomize(playlists, sp)
    else:
        # Interactive mode
        print(f"\n⚠️  This will randomize the order of tracks in ALL {len(playlists)} playlists.")
        print("   This action cannot be easily undone!")
        print("\nProceed? (y/n): ", end="")
        confirm = input().strip().lower()

        if confirm != "y":
            print("\n❌ Cancelled.")
            return

        print("\nExclude any playlists? Enter numbers separated by commas (e.g., 1,3,5) or press Enter for all: ", end="")
        exclude_input = input().strip()

        excluded_indices = set()
        if exclude_input:
            try:
                excluded_indices = {int(x.strip()) - 1 for x in exclude_input.split(",")}
                excluded_indices = {i for i in excluded_indices if 0 <= i < len(playlists)}
            except ValueError:
                print("   ⚠️  Invalid input, randomizing all playlists")

        print(f"\n🔀 Randomizing playlists...")
        print("   Note: Each playlist is randomized independently.")
        print("   Tracks stay in their original playlists.\n")
        successful, failed, skipped = run_randomize(playlists, sp, excluded_indices)

    # Summary
    print("\n" + "=" * 60)
    print("📊 Summary:")
    print(f"   ✅ Successfully randomized: {successful}")
    print(f"   ⏭️  Skipped: {skipped}")
    print(f"   ❌ Failed: {failed}")
    print("=" * 60)

    if successful > 0:
        print("\n🎉 Done! Your playlists have been randomized.")
        print("   Note: The changes may take a moment to appear in the Spotify app.")


if __name__ == "__main__":
    main()
