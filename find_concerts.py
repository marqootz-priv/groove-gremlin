#!/usr/bin/env python3
"""
Spotify Concert Finder
Finds upcoming concerts for your followed artists using Bandsintown API.
"""

import spotipy
from spotipy.oauth2 import SpotifyOAuth
import requests
import time
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import math

# Load environment variables
load_dotenv()

# Spotify credentials
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")

SCOPES = ["user-follow-read"]

# Bandsintown API (free, uses app_id for tracking)
BANDSINTOWN_APP_ID = "spotify_concert_finder"
BANDSINTOWN_BASE_URL = "https://rest.bandsintown.com"


def create_spotify_client():
    """Create authenticated Spotify client."""
    if not CLIENT_ID or not CLIENT_SECRET:
        print("❌ Missing Spotify credentials in .env file")
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


def get_followed_artists(sp):
    """Get all artists the user follows on Spotify."""
    print("\n🎵 Fetching your followed artists...")
    artists = []
    after = None

    while True:
        results = sp.current_user_followed_artists(limit=50, after=after)
        items = results["artists"]["items"]
        
        if not items:
            break

        for artist in items:
            artists.append({
                "id": artist["id"],
                "name": artist["name"],
                "genres": artist.get("genres", []),
            })

        if results["artists"]["next"]:
            after = items[-1]["id"]
        else:
            break

    print(f"✅ Found {len(artists)} followed artists")
    return artists


def get_artist_events(artist_name):
    """
    Get upcoming events for an artist from Bandsintown.
    Returns list of events or empty list if none found.
    """
    # URL encode the artist name
    encoded_name = requests.utils.quote(artist_name)
    url = f"{BANDSINTOWN_BASE_URL}/artists/{encoded_name}/events"
    
    params = {
        "app_id": BANDSINTOWN_APP_ID,
        "date": "upcoming",
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                return data
        return []
    except Exception:
        return []


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points on Earth (in miles).
    Uses the Haversine formula.
    """
    # Convert latitude and longitude from degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Radius of earth in miles
    r = 3959
    
    return c * r


def geocode_location(city=None, state=None, country=None):
    """
    Geocode a location to get latitude/longitude using Nominatim (OpenStreetMap).
    Returns (lat, lon) or (None, None) if not found.
    """
    if not any([city, state, country]):
        return None, None
    
    # Build query
    query_parts = []
    if city:
        query_parts.append(city)
    if state:
        query_parts.append(state)
    if country:
        query_parts.append(country)
    
    query = ", ".join(query_parts)
    
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": query,
            "format": "json",
            "limit": 1,
        }
        headers = {
            "User-Agent": "SpotifyConcertFinder/1.0"
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data:
                lat = float(data[0]["lat"])
                lon = float(data[0]["lon"])
                return lat, lon
    except Exception:
        pass
    
    return None, None


def filter_events_by_location(events, city=None, state=None, country=None, radius_miles=None, user_lat=None, user_lon=None):
    """
    Filter events by location criteria.
    If radius_miles is provided with coordinates, uses distance-based filtering.
    Otherwise uses string matching on city/state/country.
    """
    filtered = []
    
    # If we have coordinates and radius, use distance-based filtering
    if user_lat and user_lon and radius_miles:
        for event in events:
            venue = event.get("venue", {})
            venue_lat = venue.get("latitude")
            venue_lon = venue.get("longitude")
            
            # If venue has coordinates, calculate distance
            if venue_lat is not None and venue_lon is not None:
                try:
                    distance = haversine_distance(user_lat, user_lon, float(venue_lat), float(venue_lon))
                    if distance <= radius_miles:
                        filtered.append(event)
                except (ValueError, TypeError):
                    # Invalid coordinates, skip
                    pass
            else:
                # No coordinates for venue, fall back to string matching
                venue_city = venue.get("city", "").lower()
                venue_region = venue.get("region", "").lower()
                venue_country = venue.get("country", "").lower()
                
                match = True
                if city and city.lower() not in venue_city:
                    match = False
                if state and state.lower() not in venue_region:
                    match = False
                if country and country.lower() not in venue_country:
                    match = False
                
                if match:
                    filtered.append(event)
        return filtered
    
    # Otherwise, use string matching (original behavior)
    for event in events:
        venue = event.get("venue", {})
        venue_city = venue.get("city", "").lower()
        venue_region = venue.get("region", "").lower()
        venue_country = venue.get("country", "").lower()
        
        # If no filters, include all
        if not any([city, state, country]):
            filtered.append(event)
            continue
        
        # Check location matches
        match = True
        if city and city.lower() not in venue_city:
            match = False
        if state and state.lower() not in venue_region:
            match = False
        if country and country.lower() not in venue_country:
            match = False
            
        if match:
            filtered.append(event)
    
    return filtered


def filter_events_by_date(events, months_ahead=3):
    """Filter events within the specified number of months."""
    cutoff_date = datetime.now() + timedelta(days=months_ahead * 30)
    filtered = []
    
    for event in events:
        try:
            event_date = datetime.fromisoformat(event["datetime"].replace("Z", "+00:00"))
            if event_date.replace(tzinfo=None) <= cutoff_date:
                filtered.append(event)
        except (KeyError, ValueError):
            # Include events with unparseable dates
            filtered.append(event)
    
    return filtered


def format_event(event, artist_name, user_lat=None, user_lon=None):
    """Format an event for display."""
    venue = event.get("venue", {})
    
    # Parse date
    try:
        dt = datetime.fromisoformat(event["datetime"].replace("Z", "+00:00"))
        date_str = dt.strftime("%a, %b %d, %Y @ %I:%M %p")
    except Exception:
        date_str = event.get("datetime", "TBA")
        dt = None
    
    venue_name = venue.get("name", "TBA")
    city = venue.get("city", "")
    region = venue.get("region", "")
    country = venue.get("country", "")
    
    location_parts = [p for p in [city, region, country] if p]
    location = ", ".join(location_parts) or "Location TBA"
    
    # Calculate distance if we have coordinates
    distance_str = ""
    if user_lat and user_lon:
        venue_lat = venue.get("latitude")
        venue_lon = venue.get("longitude")
        if venue_lat is not None and venue_lon is not None:
            try:
                distance = haversine_distance(user_lat, user_lon, float(venue_lat), float(venue_lon))
                distance_str = f" ({distance:.1f} mi away)"
            except (ValueError, TypeError):
                pass
    
    ticket_url = event.get("url", "")
    
    return {
        "artist": artist_name,
        "date": date_str,
        "datetime_obj": dt,
        "venue": venue_name,
        "location": location + distance_str,
        "tickets": ticket_url,
    }


def main():
    print("=" * 60)
    print("🎤 Spotify Concert Finder")
    print("=" * 60)

    # Get location preferences
    print("\n📍 Location Filter (leave blank to see all events)")
    print("   Examples: 'San Francisco', 'CA', 'US', or 'New York, NY'")
    location_input = input("\nEnter city, state, or country: ").strip()
    
    # Parse location input
    city, state, country = None, None, None
    user_lat, user_lon = None, None
    radius_miles = None
    
    if location_input:
        parts = [p.strip() for p in location_input.split(",")]
        if len(parts) >= 2:
            city = parts[0]
            state = parts[1]
        elif len(parts) == 1:
            # Could be city, state abbrev, or country
            loc = parts[0]
            if len(loc) == 2:
                state = loc  # Likely state abbreviation
            elif loc.lower() in ["us", "usa", "uk", "canada", "australia", "germany", "france"]:
                country = loc
            else:
                city = loc
        
        # Geocode the location to get coordinates
        print(f"   🔍 Looking up coordinates for '{location_input}'...")
        user_lat, user_lon = geocode_location(city, state, country)
        
        if user_lat and user_lon:
            print(f"   ✅ Found: {user_lat:.4f}, {user_lon:.4f}")
            print("\n   Use radius-based search? (y/n, default: n): ", end="")
            use_radius = input().strip().lower() == "y"
            
            if use_radius:
                print("   Enter search radius in miles (default: 50): ", end="")
                radius_input = input().strip()
                radius_miles = float(radius_input) if radius_input.replace(".", "").isdigit() else 50
                print(f"   📍 Searching within {radius_miles} miles")
        else:
            print("   ⚠️  Could not geocode location, using text matching instead")

    # Get time range
    print("\nHow many months ahead to search? (default: 3): ", end="")
    months_input = input().strip()
    months_ahead = int(months_input) if months_input.isdigit() else 3

    # Create Spotify client and get followed artists
    sp = create_spotify_client()
    user = sp.current_user()
    print(f"\n👋 Hello, {user['display_name']}!")

    artists = get_followed_artists(sp)

    if not artists:
        print("\n⚠️  You're not following any artists on Spotify!")
        print("   Use follow_artists.py first, or follow some artists in the Spotify app.")
        return

    # Search for events
    print("\n🔍 Searching for concerts (this may take a minute)...")
    all_events = []
    artists_with_events = set()

    for i, artist in enumerate(artists):
        # Progress indicator
        print(f"   Checking {artist['name']}... ({i+1}/{len(artists)})", end="\r")
        
        events = get_artist_events(artist["name"])
        
        if events:
            # Filter by date
            events = filter_events_by_date(events, months_ahead)
            
            # Filter by location if specified
            if location_input:
                events = filter_events_by_location(
                    events, 
                    city=city, 
                    state=state, 
                    country=country,
                    radius_miles=radius_miles,
                    user_lat=user_lat,
                    user_lon=user_lon
                )
            
            for event in events:
                formatted = format_event(event, artist["name"], user_lat, user_lon)
                all_events.append(formatted)
                artists_with_events.add(artist["name"])
        
        # Rate limiting - be nice to the API
        time.sleep(0.3)

    print(" " * 60)  # Clear progress line

    if not all_events:
        print("\n😔 No upcoming concerts found for your followed artists")
        if location_input:
            print(f"   in '{location_input}' within the next {months_ahead} months.")
            print("   Try a broader search (larger area or more months).")
        return

    # Sort events by date
    all_events.sort(key=lambda x: x.get("date", ""))

    # Display results
    print(f"\n🎉 Found {len(all_events)} concerts from {len(artists_with_events)} artists!\n")
    print("=" * 60)
    
    current_month = ""
    for event in all_events:
        # Group by month
        try:
            month = event["date"].split(",")[1].strip()[:3] + " " + event["date"].split(",")[2].strip()[:4]
            if month != current_month:
                current_month = month
                print(f"\n📅 {current_month}")
                print("-" * 40)
        except Exception:
            pass

        print(f"\n🎤 {event['artist']}")
        print(f"   📆 {event['date']}")
        print(f"   📍 {event['venue']}")
        print(f"   🌍 {event['location']}")
        if event['tickets']:
            print(f"   🎟️  {event['tickets']}")

    # Summary
    print("\n" + "=" * 60)
    print(f"📊 Summary: {len(all_events)} concerts, {len(artists_with_events)} artists")
    print("=" * 60)

    # Option to save to file
    print("\nSave results to file? (y/n): ", end="")
    if input().strip().lower() == "y":
        # Get the directory where the script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        filename = f"concerts_{datetime.now().strftime('%Y%m%d')}.txt"
        filepath = os.path.join(script_dir, filename)
        with open(filepath, "w") as f:
            f.write("Concerts for Followed Artists\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            if location_input:
                f.write(f"Location: {location_input}\n")
            f.write(f"Time range: Next {months_ahead} months\n")
            f.write("=" * 60 + "\n\n")
            
            for event in all_events:
                f.write(f"{event['artist']}\n")
                f.write(f"  Date: {event['date']}\n")
                f.write(f"  Venue: {event['venue']}\n")
                f.write(f"  Location: {event['location']}\n")
                if event['tickets']:
                    f.write(f"  Tickets: {event['tickets']}\n")
                f.write("\n")
        
        print(f"✅ Saved to {filepath}")


if __name__ == "__main__":
    main()

