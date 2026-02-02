#!/usr/bin/env python3
"""
Spotify to Instagram Account Finder
Finds Instagram accounts for artists you follow on Spotify.

Modes:
1. Safe mode (default): Finds accounts and generates a list for manual following
2. Browser automation (optional): Uses Selenium to automate following (RISKY - see warnings)
"""

import spotipy
from spotipy.oauth2 import SpotifyOAuth
import requests
import time
import os
import json
import csv
from dotenv import load_dotenv
from urllib.parse import quote
import re

from apify_client import ApifyClient

# Load environment variables
load_dotenv()

# Spotify credentials
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")
APIFY_TOKEN = os.getenv("APIFY_API_TOKEN") or os.getenv("APIFY_TOKEN")

SCOPES = ["user-follow-read"]

# Optional known handles to avoid search flakiness (fill in as needed)
KNOWN_HANDLES = {
    # "Artist Name": "handle",
}


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
                "popularity": artist.get("popularity", 0),
            })

        if results["artists"]["next"]:
            after = items[-1]["id"]
        else:
            break

    print(f"✅ Found {len(artists)} followed artists")
    return artists


def search_instagram_via_musicbrainz(artist_name):
    """
    Search MusicBrainz for artist and extract Instagram URL from relations.
    MusicBrainz stores social media links in artist 'url-relations'.
    Returns Instagram handle or None.
    """
    try:
        # Step 1: Search for artist by name
        search_url = "https://musicbrainz.org/ws/2/artist"
        params = {
            "query": f'artist:"{artist_name}"',
            "fmt": "json",
            "limit": 1
        }
        headers = {
            "User-Agent": "GrooveGremlin/1.0 (spotify-tools)"
        }

        response = requests.get(search_url, params=params, headers=headers, timeout=10)
        if response.status_code != 200:
            return None

        data = response.json()
        artists = data.get("artists", [])
        if not artists:
            return None

        # Get the best match (highest score)
        artist = artists[0]
        mbid = artist.get("id")
        if not mbid:
            return None

        # MusicBrainz requires 1 second between requests
        time.sleep(1)

        # Step 2: Get artist with URL relationships
        artist_url = f"https://musicbrainz.org/ws/2/artist/{mbid}"
        params = {
            "inc": "url-rels",
            "fmt": "json"
        }

        response = requests.get(artist_url, params=params, headers=headers, timeout=10)
        if response.status_code != 200:
            return None

        artist_data = response.json()
        relations = artist_data.get("relations", [])

        # Step 3: Look for Instagram in relations
        for rel in relations:
            rel_type = rel.get("type", "").lower()
            url_info = rel.get("url", {})
            resource = url_info.get("resource", "")

            # MusicBrainz uses "social network" type for social media links
            if rel_type == "social network" and "instagram.com" in resource:
                # Extract handle from URL
                clean_url = resource.split("?")[0].rstrip("/")
                if "/p/" not in clean_url and "/reel/" not in clean_url:
                    # Extract username from URL
                    parts = clean_url.split("instagram.com/")
                    if len(parts) > 1:
                        handle = parts[1].split("/")[0]
                        if handle:
                            return handle

        return None

    except Exception:
        return None


def search_instagram_via_wikidata(artist_name):
    """
    Query Wikidata SPARQL endpoint for Instagram username.
    Wikidata property P2003 = "Instagram username"
    Returns Instagram handle or None.
    """
    try:
        # SPARQL query to find artist and their Instagram username
        sparql_query = f"""
        SELECT ?instagram WHERE {{
          {{ ?item wdt:P31 wd:Q5 . }}
          UNION
          {{ ?item wdt:P31 wd:Q215380 . }}
          UNION
          {{ ?item wdt:P31 wd:Q105756498 . }}
          ?item rdfs:label "{artist_name}"@en .
          ?item wdt:P2003 ?instagram .
        }}
        LIMIT 1
        """

        endpoint = "https://query.wikidata.org/sparql"
        headers = {
            "Accept": "application/json",
            "User-Agent": "GrooveGremlin/1.0 (spotify-tools)"
        }
        params = {"query": sparql_query}

        response = requests.get(endpoint, headers=headers, params=params, timeout=10)
        if response.status_code != 200:
            return None

        data = response.json()
        bindings = data.get("results", {}).get("bindings", [])

        if bindings:
            instagram_username = bindings[0].get("instagram", {}).get("value", "")
            if instagram_username:
                return instagram_username

        return None

    except Exception:
        return None


def search_instagram_handle(artist_name):
    """
    Search for an Instagram account using web search.
    Returns Instagram handle/username if found, None otherwise.
    """
    # Known handles shortcut
    if artist_name in KNOWN_HANDLES:
        return KNOWN_HANDLES[artist_name]

    # Strategy 1: MusicBrainz (structured data, reliable for musicians)
    handle = search_instagram_via_musicbrainz(artist_name)
    if handle:
        return handle

    # Strategy 2: Wikidata (P2003 = Instagram username)
    handle = search_instagram_via_wikidata(artist_name)
    if handle:
        return handle

    # Strategy 3: Apify Google Search actor if token available
    if APIFY_TOKEN:
        handle = search_instagram_handle_apify_google(artist_name)
        if handle:
            return handle

    # Strategy 4: Try multiple web search strategies
    search_queries = [
        f"{artist_name} instagram",
        f'"{artist_name}" instagram official',
        f"{artist_name} @instagram",
    ]
    
    for query in search_queries:
        try:
            # Use DuckDuckGo instant answer API (no auth required)
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_redirect": "1",
            }
            
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                # Check if there's a related topic or answer
                if data.get("RelatedTopics"):
                    for topic in data["RelatedTopics"]:
                        text = topic.get("Text", "").lower()
                        if "instagram.com" in text or "@" in text:
                            # Try to extract handle
                            if "instagram.com/" in text:
                                parts = text.split("instagram.com/")
                                if len(parts) > 1:
                                    handle = parts[1].split()[0].split("/")[0].split("?")[0]
                                    if handle and len(handle) > 0:
                                        return handle.strip()
            
            time.sleep(0.5)  # Rate limiting
        except Exception:
            continue
    
    return None


def search_instagram_handle_apify_google(artist_name):
    """
    Use Apify Google Search Results Scraper to find Instagram handles.
    Returns handle if found, otherwise None.
    """
    try:
        client = ApifyClient(APIFY_TOKEN)
        run = client.actor("apify/google-search-scraper").call(
            run_input={
                "queries": f"{artist_name} instagram",  # Single string, not array
                "maxPagesPerQuery": 1,
                "resultsPerPage": 10,
                "countryCode": "us",
                "languageCode": "en",
            }
        )
        items = client.dataset(run["defaultDatasetId"]).list_items().items

        instagram_urls = []
        for item in items:
            for result in item.get("organicResults", []):
                url = result.get("url", "")
                if "instagram.com" in url:
                    clean = url.split("?")[0].split("#")[0].rstrip("/")
                    instagram_urls.append(clean)

        # Extract the first plausible profile handle
        for url in instagram_urls:
            m = re.search(r"instagram\\.com/([^/?#]+)/?$", url)
            if m:
                handle = m.group(1)
                # Skip non-profile paths
                if handle.lower() not in {"explore", "accounts", "p"}:
                    return handle
    except Exception:
        return None
    return None


def find_instagram_via_spotify_artist(sp, artist_id):
    """
    Check if Spotify artist profile has external links to Instagram.
    Returns Instagram handle if found.
    """
    try:
        artist = sp.artist(artist_id)
        external_urls = artist.get("external_urls", {})
        
        # Check if there's a link to Instagram in external URLs
        # Spotify doesn't directly provide Instagram, but we can check
        # the artist's profile page might have it
        
        # Also check if there's any social media info
        # (Spotify API doesn't provide this directly, but worth checking)
        
    except Exception:
        pass
    
    return None


def generate_instagram_url(handle):
    """Generate Instagram URL from handle."""
    if not handle:
        return None
    # Remove @ if present
    handle = handle.lstrip("@")
    return f"https://www.instagram.com/{handle}/"


def main():
    print("=" * 60)
    print("📸 Instagram Account Finder for Spotify Artists")
    print("=" * 60)
    print("\nThis script finds Instagram accounts for your followed artists.")
    print("   • Exports data in formats compatible with PhantomBuster/Apify")
    print("   • These services are RECOMMENDED for safe automation")
    print("   • Instagram API doesn't allow automated following directly")
    print("   • Supports multiple users - each uses their own credentials\n")
    
    # Create Spotify client
    sp = create_spotify_client()
    user = sp.current_user()
    spotify_username = user['display_name'] or user.get('id', 'user')
    print(f"👋 Hello, {user['display_name']}!")
    
    # Get followed artists
    artists = get_followed_artists(sp)
    
    if not artists:
        print("\n⚠️  You're not following any artists on Spotify!")
        return
    
    # Ask how to search
    print("\n🔍 Search Options:")
    print("   1. Quick search (faster, may miss some accounts)")
    print("   2. Thorough search (slower, more comprehensive)")
    print("   3. Manual mode (just generate Instagram URLs to check)")
    choice = input("\nSelect option (1-3, default: 1): ").strip() or "1"
    
    quick_mode = choice == "1"
    manual_mode = choice == "3"
    
    if manual_mode:
        print("\n📝 Generating Instagram URLs for manual checking...")
        print("   (You'll need to visit each URL to verify and follow)")
    
    # Search for Instagram accounts
    print(f"\n🔍 Searching for Instagram accounts...")
    if not manual_mode:
        print("   (This may take a while for many artists)\n")
    
    results = []
    found_count = 0
    not_found_count = 0
    
    for i, artist in enumerate(artists):
        artist_name = artist["name"]
        print(f"   Checking {artist_name}... ({i+1}/{len(artists)})", end="\r")
        
        instagram_handle = None
        instagram_url = None
        
        if not manual_mode:
            # Try to find Instagram account
            instagram_handle = search_instagram_handle(artist_name)
            
            if instagram_handle:
                instagram_url = generate_instagram_url(instagram_handle)
                found_count += 1
            else:
                not_found_count += 1
                # Generate a potential URL based on artist name
                # (common pattern: artist name as handle)
                potential_handle = artist_name.lower().replace(" ", "").replace(".", "").replace("'", "")
                instagram_url = generate_instagram_url(potential_handle)
        else:
            # Manual mode: just generate potential URL
            potential_handle = artist_name.lower().replace(" ", "").replace(".", "").replace("'", "")
            instagram_url = generate_instagram_url(potential_handle)
        
        results.append({
            "artist": artist_name,
            "instagram_handle": instagram_handle,
            "instagram_url": instagram_url,
            "found": instagram_handle is not None,
        })
        
        if not quick_mode and not manual_mode:
            time.sleep(1)  # Slower for thorough search
    
    print(" " * 60)  # Clear progress line
    
    # Display results
    print("\n" + "=" * 60)
    print("📊 Results:")
    print("=" * 60)
    
    found_results = [r for r in results if r["found"]]
    not_found_results = [r for r in results if not r["found"]]
    
    if found_results:
        print(f"\n✅ Found Instagram accounts ({len(found_results)}):")
        print("-" * 60)
        for result in found_results:
            print(f"\n🎤 {result['artist']}")
            print(f"   📸 @{result['instagram_handle']}")
            print(f"   🔗 {result['instagram_url']}")
    
    if not_found_results:
        print(f"\n❓ Potential Instagram accounts ({len(not_found_results)}):")
        print("   (These are guesses - verify before following)")
        print("-" * 60)
        for result in not_found_results[:20]:  # Show first 20
            print(f"\n🎤 {result['artist']}")
            print(f"   🔗 {result['instagram_url']}")
        if len(not_found_results) > 20:
            print(f"\n   ... and {len(not_found_results) - 20} more")
    
    # Save to file
    print("\n" + "=" * 60)
    save_choice = input("Save results to file? (y/n): ").strip().lower()
    
    if save_choice == "y":
        # Get the directory where the script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        timestamp = int(time.time())
        
        # Optional: Include username in filename for multi-user setups
        # Uncomment the next line if you want user-specific filenames
        # username_suffix = f"_{spotify_username.replace(' ', '_')}" if spotify_username else ""
        username_suffix = ""  # Keep empty for now (timestamp is usually enough)
        
        # Save as JSON
        json_filename = f"instagram_accounts{username_suffix}_{timestamp}.json"
        json_path = os.path.join(script_dir, json_filename)
        with open(json_path, "w") as f:
            json.dump(results, f, indent=2)
        
        # Save as CSV for PhantomBuster/Apify (one URL per line)
        csv_filename = f"instagram_accounts{username_suffix}_{timestamp}.csv"
        csv_path = os.path.join(script_dir, csv_filename)
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["artist", "instagram_handle", "instagram_url", "found"])  # Header
            for result in results:
                writer.writerow([
                    result["artist"],
                    result["instagram_handle"] or "",
                    result["instagram_url"] or "",
                    "Yes" if result["found"] else "No"
                ])
        
        # Save as simple text file (one URL per line) for easy import
        urls_filename = f"instagram_urls{username_suffix}_{timestamp}.txt"
        urls_path = os.path.join(script_dir, urls_filename)
        urls_list = []
        with open(urls_path, "w") as f:
            for result in results:
                if result["instagram_url"]:
                    url = result["instagram_url"]
                    f.write(f"{url}\n")
                    urls_list.append(url)
        
        # Save as Apify input format (ready to use, just add credentials)
        apify_input_filename = f"instagram_urls{username_suffix}_{timestamp}_apify_input.json"
        apify_input_path = os.path.join(script_dir, apify_input_filename)
        apify_input = {
            "urls": urls_list,
            "delay_min": 2,
            "delay_max": 4,
            "max_follows": 40,
            "headless": False
            # Note: Add instagram_username and instagram_password before using
        }
        with open(apify_input_path, "w") as f:
            json.dump(apify_input, f, indent=2)
        
        # Save as text file with clickable links
        txt_filename = f"instagram_accounts{username_suffix}_{timestamp}.txt"
        txt_path = os.path.join(script_dir, txt_filename)
        with open(txt_path, "w") as f:
            f.write("Instagram Accounts for Followed Artists\n")
            f.write("=" * 60 + "\n\n")
            
            if found_results:
                f.write(f"✅ Found Accounts ({len(found_results)}):\n")
                f.write("-" * 60 + "\n\n")
                for result in found_results:
                    f.write(f"{result['artist']}\n")
                    f.write(f"  Handle: @{result['instagram_handle']}\n")
                    f.write(f"  URL: {result['instagram_url']}\n\n")
            
            if not_found_results:
                f.write(f"\n❓ Potential Accounts ({len(not_found_results)}):\n")
                f.write("(Verify these before following)\n")
                f.write("-" * 60 + "\n\n")
                for result in not_found_results:
                    f.write(f"{result['artist']}\n")
                    f.write(f"  URL: {result['instagram_url']}\n\n")
        
        print(f"\n✅ Saved to:")
        print(f"   JSON: {json_path}")
        print(f"   CSV (for PhantomBuster/Apify): {csv_path}")
        print(f"   URLs (one per line): {urls_path}")
        print(f"   📦 Apify Input (ready to use): {apify_input_path}")
        print(f"   Text (readable): {txt_path}")
        print(f"\n💡 The Apify input file is ready - just add your Instagram credentials!")
        print(f"   Edit {apify_input_filename} and add:")
        print(f"     - instagram_username")
        print(f"     - instagram_password")
    
    # Option to open in browser
    if found_results:
        print("\n" + "=" * 60)
        open_choice = input("Open found Instagram accounts in browser? (y/n): ").strip().lower()
        if open_choice == "y":
            import webbrowser
            for result in found_results:
                webbrowser.open(result["instagram_url"])
                time.sleep(0.5)  # Small delay between opens
    
    # Recommend third-party services
    if found_results:
        print("\n" + "=" * 60)
        print("🤖 AUTOMATED FOLLOWING OPTIONS")
        print("=" * 60)
        print("\n💡 RECOMMENDED: Use PhantomBuster or Apify")
        print("   These services are safer and more reliable than raw automation:")
        print("   • Better anti-bot detection handling")
        print("   • Managed rate limiting")
        print("   • Cookie/session management")
        print("   • Lower risk of account restrictions")
        print("\n   Services:")
        print("   • PhantomBuster: https://phantombuster.com (Instagram Follow automation)")
        print("   • Apify: https://apify.com (Instagram automation actors)")
        print("\n   📖 Setup Guide: See APIFY_SETUP.md for detailed instructions")
        print("\n   The CSV file has been saved and can be imported into these services.")
        print("   Or use the URLs file (one URL per line) for easy import.")
        
        print("\n" + "-" * 60)
        print("⚠️  ALTERNATIVE: Raw Selenium Automation (NOT RECOMMENDED)")
        print("-" * 60)
        print("\n⚠️  WARNING: Instagram actively fights automation!")
        print("   Risks include:")
        print("   • Action blocks (24-72 hour cooldowns)")
        print("   • Temporary restrictions (slower follow limits)")
        print("   • Permanent account suspension")
        print("\n   Safe limits: <40 follows/hour, spaced over time")
        print("   This feature uses Selenium browser automation.")
        print("\n   ⚠️  We STRONGLY recommend using PhantomBuster/Apify instead!")
        
        auto_choice = input("\nUse raw Selenium automation anyway? (NOT RECOMMENDED) (y/n): ").strip().lower()
        
        if auto_choice == "y":
            try:
                from selenium import webdriver
                from selenium.webdriver.common.by import By
                from selenium.webdriver.common.keys import Keys
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                from selenium.common.exceptions import TimeoutException, NoSuchElementException
                import random
                
                print("\n🔧 Setting up browser automation...")
                print("   Make sure Chrome/Chromium is installed")
                print("   ChromeDriver will be needed (install via: brew install chromedriver)")
                
                # Final confirmation
                print("\n⚠️  FINAL WARNING: This will automate following on Instagram.")
                print("   Your account may be restricted or banned.")
                final_confirm = input("   Type 'YES' to proceed: ").strip()
                
                if final_confirm != "YES":
                    print("\n❌ Automation cancelled. Use the saved list to follow manually.")
                    return
                
                # Initialize browser
                options = webdriver.ChromeOptions()
                # Uncomment to run headless (no visible browser)
                # options.add_argument('--headless')
                options.add_argument('--disable-blink-features=AutomationControlled')
                options.add_experimental_option("excludeSwitches", ["enable-automation"])
                options.add_experimental_option('useAutomationExtension', False)
                
                driver = webdriver.Chrome(options=options)
                
                print("\n🌐 Opening Instagram...")
                driver.get("https://www.instagram.com/accounts/login/")
                
                print("\n⏸️  Please log in to Instagram in the browser window.")
                print("   After logging in, press Enter here to continue...")
                input()
                
                # Follow accounts with rate limiting
                print(f"\n🤖 Starting to follow {len(found_results)} accounts...")
                print("   Rate limit: ~2-3 seconds between follows (safe limit)")
                
                followed_count = 0
                failed_count = 0
                
                for i, result in enumerate(found_results[:40], 1):  # Limit to 40 per session
                    try:
                        artist_name = result['artist']
                        instagram_url = result['instagram_url']
                        
                        print(f"\n[{i}/{min(len(found_results), 40)}] {artist_name}...", end=" ")
                        
                        # Navigate to profile
                        driver.get(instagram_url)
                        
                        # Wait for page to load
                        time.sleep(2 + random.uniform(0, 1))  # Random delay 2-3 seconds
                        
                        # Look for Follow button
                        try:
                            # Try different possible button texts/locations
                            follow_selectors = [
                                "//button[contains(text(), 'Follow')]",
                                "//button[contains(., 'Follow')]",
                                "//button[@type='button' and contains(., 'Follow')]",
                            ]
                            
                            follow_button = None
                            for selector in follow_selectors:
                                try:
                                    follow_button = WebDriverWait(driver, 3).until(
                                        EC.element_to_be_clickable((By.XPATH, selector))
                                    )
                                    break
                                except TimeoutException:
                                    continue
                            
                            if follow_button:
                                # Check if already following
                                button_text = follow_button.text.strip()
                                if button_text in ["Following", "Requested"]:
                                    print("Already following")
                                    continue
                                
                                # Click follow
                                follow_button.click()
                                followed_count += 1
                                print("✅ Followed")
                                
                                # Random delay between follows (2-4 seconds)
                                time.sleep(2 + random.uniform(0, 2))
                            else:
                                print("❌ Follow button not found")
                                failed_count += 1
                                
                        except (TimeoutException, NoSuchElementException) as e:
                            print(f"❌ Could not find follow button")
                            failed_count += 1
                        
                    except Exception as e:
                        print(f"❌ Error: {str(e)[:50]}")
                        failed_count += 1
                        time.sleep(1)
                    
                    # Extra delay every 10 follows
                    if i % 10 == 0:
                        print(f"\n   ⏸️  Pausing for 10 seconds (rate limiting)...")
                        time.sleep(10)
                
                print("\n" + "=" * 60)
                print("📊 Automation Summary:")
                print(f"   ✅ Successfully followed: {followed_count}")
                print(f"   ❌ Failed: {failed_count}")
                print("=" * 60)
                
                print("\n⚠️  IMPORTANT:")
                print("   • Wait at least 1 hour before running again")
                print("   • Keep total follows under 40 per hour")
                print("   • Spread automation over multiple days")
                print("   • Monitor your account for restrictions")
                
                input("\nPress Enter to close the browser...")
                driver.quit()
                
            except ImportError:
                print("\n❌ Selenium not installed.")
                print("   Install with: pip install selenium")
                print("   Also install ChromeDriver: brew install chromedriver")
            except Exception as e:
                print(f"\n❌ Automation error: {e}")
                print("   Use the saved list to follow manually instead.")
        else:
            print("\n💡 Tip: Use the generated list to manually follow artists on Instagram.")
    else:
        print("\n💡 Tips:")
        print("   • Use the CSV file with PhantomBuster or Apify for safe automation")
        print("   • Or manually follow using the generated list")
        print("   • Instagram doesn't allow automated following via official API")


if __name__ == "__main__":
    main()
