#!/usr/bin/env python3
"""
Spotify Artist Follower Script
Automatically follows all artists from your liked/saved tracks.
"""

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from collections import defaultdict
import time
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Spotify API credentials - set these in .env file or environment
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")

# Required scopes for this script
SCOPES = [
    "user-library-read",      # Read saved tracks
    "user-follow-read",       # Check followed artists
    "user-follow-modify",     # Follow/unfollow artists
    "user-top-read",          # Read top artists (optional feature)
]


def create_spotify_client():
    """Create and return an authenticated Spotify client."""
    if not CLIENT_ID or not CLIENT_SECRET:
        print("❌ Error: Missing Spotify credentials!")
        print("\nPlease set up your credentials:")
        print("  1. Go to https://developer.spotify.com/dashboard")
        print("  2. Create an app (or use existing one)")
        print("  3. Copy Client ID and Client Secret")
        print("  4. Add redirect URI: http://localhost:8888/callback")
        print("  5. Create a .env file with:")
        print("     SPOTIFY_CLIENT_ID=your_client_id")
        print("     SPOTIFY_CLIENT_SECRET=your_client_secret")
        raise SystemExit(1)

    return spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            redirect_uri=REDIRECT_URI,
            scope=" ".join(SCOPES),
            cache_path=".spotify_cache",
        )
    )


def get_saved_tracks_artists(sp):
    """
    Fetch all artists from user's saved/liked tracks.
    Returns a dict of {artist_id: artist_name}
    """
    print("\n📚 Fetching your saved tracks...")
    artists = {}
    offset = 0
    limit = 50
    total = None

    while True:
        results = sp.current_user_saved_tracks(limit=limit, offset=offset)
        
        if total is None:
            total = results["total"]
            print(f"   Found {total} saved tracks to process")

        if not results["items"]:
            break

        for item in results["items"]:
            track = item["track"]
            if track:  # Sometimes tracks can be None (deleted)
                for artist in track["artists"]:
                    artists[artist["id"]] = artist["name"]

        offset += limit
        processed = min(offset, total)
        print(f"   Processed {processed}/{total} tracks...", end="\r")

        # Small delay to avoid rate limiting
        time.sleep(0.1)

    print(f"\n✅ Found {len(artists)} unique artists in your saved tracks")
    return artists


def get_top_artists(sp, time_range="medium_term"):
    """
    Fetch user's top artists.
    time_range: short_term (~4 weeks), medium_term (~6 months), long_term (years)
    Returns a dict of {artist_id: artist_name}
    """
    print(f"\n🎵 Fetching your top artists ({time_range})...")
    artists = {}
    offset = 0
    limit = 50

    while True:
        results = sp.current_user_top_artists(limit=limit, offset=offset, time_range=time_range)
        
        if not results["items"]:
            break

        for artist in results["items"]:
            artists[artist["id"]] = artist["name"]

        offset += limit
        if offset >= results["total"]:
            break

    print(f"✅ Found {len(artists)} top artists")
    return artists


def get_followed_artists(sp):
    """
    Fetch all artists the user currently follows.
    Returns a set of artist IDs.
    """
    print("\n👥 Fetching artists you already follow...")
    followed = set()
    after = None

    while True:
        results = sp.current_user_followed_artists(limit=50, after=after)
        artists = results["artists"]
        
        if not artists["items"]:
            break

        for artist in artists["items"]:
            followed.add(artist["id"])

        if artists["next"]:
            after = artists["items"][-1]["id"]
        else:
            break

    print(f"✅ You currently follow {len(followed)} artists")
    return followed


def follow_artists(sp, artist_ids, artist_names):
    """
    Follow a list of artists.
    Spotify API allows following up to 50 artists at a time.
    """
    if not artist_ids:
        print("\n✨ No new artists to follow!")
        return 0

    print(f"\n🎯 Following {len(artist_ids)} new artists...")
    
    # Convert to list if it's a set
    artist_list = list(artist_ids)
    followed_count = 0

    # Process in batches of 50
    for i in range(0, len(artist_list), 50):
        batch = artist_list[i:i + 50]
        try:
            sp.user_follow_artists(batch)
            followed_count += len(batch)
            
            # Show some of the artists being followed
            for aid in batch[:3]:
                if aid in artist_names:
                    print(f"   ✓ Followed: {artist_names[aid]}")
            if len(batch) > 3:
                print(f"   ... and {len(batch) - 3} more")
                
            time.sleep(0.2)  # Rate limiting
        except Exception as e:
            print(f"   ⚠️  Error following batch: {e}")

    return followed_count


def main():
    print("=" * 50)
    print("🎧 Spotify Artist Follower")
    print("=" * 50)

    # Create authenticated client
    sp = create_spotify_client()

    # Get current user info
    user = sp.current_user()
    print(f"\n👋 Hello, {user['display_name']}!")

    # Gather artists from different sources
    all_artists = {}

    # Get artists from saved tracks
    saved_artists = get_saved_tracks_artists(sp)
    all_artists.update(saved_artists)

    # Optionally also get top artists
    print("\nInclude top artists as well? (y/n): ", end="")
    include_top = input().strip().lower()
    if include_top == "y":
        for time_range in ["short_term", "medium_term", "long_term"]:
            top_artists = get_top_artists(sp, time_range)
            all_artists.update(top_artists)

    # Get currently followed artists
    followed = get_followed_artists(sp)

    # Find artists not yet followed
    to_follow = set(all_artists.keys()) - followed
    
    print(f"\n📊 Summary:")
    print(f"   Total unique artists found: {len(all_artists)}")
    print(f"   Already following: {len(followed)}")
    print(f"   New artists to follow: {len(to_follow)}")

    if not to_follow:
        print("\n✨ You're already following all artists from your saved tracks!")
        return

    # Show preview of artists to follow
    print("\n🎤 Artists to follow (preview):")
    preview_list = list(to_follow)[:10]
    for aid in preview_list:
        print(f"   • {all_artists[aid]}")
    if len(to_follow) > 10:
        print(f"   ... and {len(to_follow) - 10} more")

    # Confirm before following
    print(f"\n⚠️  Ready to follow {len(to_follow)} artists.")
    print("Proceed? (y/n): ", end="")
    confirm = input().strip().lower()

    if confirm != "y":
        print("\n❌ Cancelled.")
        return

    # Follow the artists
    count = follow_artists(sp, to_follow, all_artists)
    
    print("\n" + "=" * 50)
    print(f"🎉 Done! Successfully followed {count} new artists!")
    print("=" * 50)


if __name__ == "__main__":
    main()

