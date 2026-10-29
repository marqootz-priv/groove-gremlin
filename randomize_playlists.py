#!/usr/bin/env python3
"""
Spotify Playlist Randomizer
Randomizes the order of tracks in all your playlists.
"""

import spotipy
from spotipy.oauth2 import SpotifyOAuth
import argparse
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
CACHE_PATH = os.getenv("SPOTIFY_CACHE_PATH", ".spotify_cache")

# Required scopes
SCOPES = [
    "playlist-read-private",      # Read private playlists
    "playlist-read-collaborative", # Read collaborative playlists
    "playlist-modify-public",     # Modify public playlists
    "playlist-modify-private",    # Modify private playlists
]


def create_spotify_client(headless=False):
    """Create authenticated Spotify client.

    In headless mode there is no browser to log in with, so a token must
    already be cached; fail fast rather than wait on a prompt nobody sees.
    """
    if not CLIENT_ID or not CLIENT_SECRET:
        print("❌ Missing Spotify credentials in .env file")
        raise SystemExit(1)

    auth_manager = SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=" ".join(SCOPES),
        cache_path=CACHE_PATH,
        open_browser=not headless,
    )
    if headless and not auth_manager.validate_token(auth_manager.cache_handler.get_cached_token()):
        print(f"❌ No valid cached token at {CACHE_PATH}; run once interactively to log in")
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
                # For playlists with >100 tracks, replace with the first 100,
                # then add the rest, so the playlist is never left empty
                sp.playlist_replace_items(playlist_id, shuffled[:100])
                
                # Then add the remaining tracks in batches of 100 (all to the same playlist)
                for i in range(100, len(shuffled), 100):
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


def parse_args():
    parser = argparse.ArgumentParser(description="Randomize the order of tracks in your playlists.")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="run unattended: no prompts, never open a browser")
    parser.add_argument("--exclude", default=os.getenv("RANDOMIZE_EXCLUDE", ""),
                        help="comma-separated playlist names to skip (or set RANDOMIZE_EXCLUDE)")
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 60)
    print("🔀 Spotify Playlist Randomizer")
    print("=" * 60)
    
    # Create Spotify client
    sp = create_spotify_client(headless=args.yes)
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
    
    excluded_names = {n.strip().lower() for n in args.exclude.split(",") if n.strip()}
    excluded_indices = {i for i, p in enumerate(playlists) if p["name"].lower() in excluded_names}
    
    if not args.yes:
        # Ask for confirmation
        print(f"\n⚠️  This will randomize the order of tracks in ALL {len(playlists)} playlists.")
        print("   This action cannot be easily undone!")
        print("\nProceed? (y/n): ", end="")
        confirm = input().strip().lower()
        
        if confirm != "y":
            print("\n❌ Cancelled.")
            return
        
        # Ask if they want to exclude certain playlists
        print("\nExclude any playlists? Enter numbers separated by commas (e.g., 1,3,5) or press Enter for all: ", end="")
        exclude_input = input().strip()
    else:
        exclude_input = ""
    
    if exclude_input:
        try:
            picked = {int(x.strip()) - 1 for x in exclude_input.split(",")}
            excluded_indices |= {i for i in picked if 0 <= i < len(playlists)}
        except ValueError:
            print("   ⚠️  Invalid input, randomizing all playlists")
    
    # Randomize playlists
    print(f"\n🔀 Randomizing playlists...")
    print("   Note: Each playlist is randomized independently.")
    print("   Tracks stay in their original playlists.\n")
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
        
        # Rate limiting
        time.sleep(0.2)
    
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
