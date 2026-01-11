"""
Background worker tasks for processing jobs.
Uses RQ (Redis Queue) for simple job processing.
"""

from redis import Redis
from redis import from_url as redis_from_url
from rq import Queue
from app import app, db, User, Job
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
import json
import time
import random
import requests
from datetime import datetime, timedelta
import os

# Use REDIS_URL if available (Heroku), otherwise fall back to localhost
redis_url = os.getenv('REDIS_URL')
if redis_url:
    # Handle both redis:// and rediss:// (SSL) URLs
    # For Heroku Redis with SSL, we need to disable certificate verification
    if redis_url.startswith('rediss://'):
        redis_conn = redis_from_url(redis_url, ssl_cert_reqs=None)
    else:
        redis_conn = redis_from_url(redis_url)
else:
    # Fallback to localhost for development
    redis_conn = Redis(host=os.getenv('REDIS_HOST', 'localhost'), 
                       port=int(os.getenv('REDIS_PORT', 6379)),
                       db=0)

q = Queue('spotify_tools', connection=redis_conn)


def update_job_progress(job, percent, message, log_entry=None):
    """Update job progress and optionally add to execution log"""
    job.progress_percent = percent
    job.progress_message = message
    if log_entry:
        current_log = job.execution_log or ''
        timestamp = datetime.utcnow().strftime('%H:%M:%S')
        job.execution_log = current_log + f"[{timestamp}] {log_entry}\n"
    db.session.commit()


def get_user_spotify_client(user):
    """Get authenticated Spotify client for a user."""
    if not user.spotify_access_token:
        return None
    
    # Check if token needs refresh
    if user.spotify_token_expires_at and user.spotify_token_expires_at <= datetime.utcnow():
        # Refresh token
        auth_manager = SpotifyOAuth(
            client_id=os.getenv('SPOTIFY_CLIENT_ID'),
            client_secret=os.getenv('SPOTIFY_CLIENT_SECRET'),
            redirect_uri=os.getenv('SPOTIFY_REDIRECT_URI'),
            cache_path=None
        )
        token_info = auth_manager.refresh_access_token(user.spotify_refresh_token)
        user.spotify_access_token = token_info['access_token']
        user.spotify_token_expires_at = datetime.fromtimestamp(token_info['expires_at'])
        db.session.commit()
    
    return Spotify(auth=user.spotify_access_token)


def follow_artists_task(user_id, job_id, include_top_artists=False):
    """Follow artists from user's saved tracks and optionally top artists."""
    with app.app_context():
        user = User.query.get(user_id)
        job = Job.query.get(job_id)
        
        if not user or not job:
            return
        
        job.status = 'running'
        update_job_progress(job, 0, "Starting...", "Initializing Spotify connection")
        db.session.commit()
        
        try:
            sp = get_user_spotify_client(user)
            if not sp:
                raise Exception("Spotify not connected")
            
            update_job_progress(job, 10, "Fetching saved tracks...", "Connected to Spotify API")
            
            # Get saved tracks artists
            artists = {}
            offset = 0
            limit = 50
            total_tracks = None
            
            while True:
                results = sp.current_user_saved_tracks(limit=limit, offset=offset)
                if total_tracks is None:
                    total_tracks = results["total"]
                    update_job_progress(job, 15, f"Found {total_tracks} saved tracks", f"Processing {total_tracks} saved tracks")
                
                if not results["items"]:
                    break
                
                for item in results["items"]:
                    track = item["track"]
                    if track:
                        for artist in track["artists"]:
                            artists[artist["id"]] = artist["name"]
                
                offset += limit
                progress = min(15 + int((offset / total_tracks) * 30), 45)
                update_job_progress(job, progress, f"Processing tracks: {min(offset, total_tracks)}/{total_tracks}", 
                                  f"Processed {min(offset, total_tracks)}/{total_tracks} tracks, found {len(artists)} unique artists")
                
                if offset >= results["total"]:
                    break
                time.sleep(0.1)
            
            # Optionally include top artists
            if include_top_artists:
                update_job_progress(job, 45, "Fetching top artists...", "Including top artists from all time ranges")
                for time_range in ["short_term", "medium_term", "long_term"]:
                    try:
                        offset = 0
                        while True:
                            results = sp.current_user_top_artists(limit=50, offset=offset, time_range=time_range)
                            if not results["items"]:
                                break
                            for artist in results["items"]:
                                artists[artist["id"]] = artist["name"]
                            offset += 50
                            if offset >= results["total"]:
                                break
                        time.sleep(0.1)
                    except Exception as e:
                        update_job_progress(job, 50, "Fetching top artists...", f"Warning: Could not fetch {time_range} top artists: {str(e)}")
            
            update_job_progress(job, 50, f"Found {len(artists)} unique artists", f"Total unique artists: {len(artists)}")
            
            # Get currently followed artists
            update_job_progress(job, 55, "Checking currently followed artists...", "Fetching list of already-followed artists")
            followed = set()
            after = None
            while True:
                results = sp.current_user_followed_artists(limit=50, after=after)
                items = results["artists"]["items"]
                if not items:
                    break
                for artist in items:
                    followed.add(artist["id"])
                if results["artists"]["next"]:
                    after = items[-1]["id"]
                else:
                    break
            
            # Find artists to follow
            to_follow = set(artists.keys()) - followed
            update_job_progress(job, 60, f"Calculating artists to follow...", 
                              f"Already following: {len(followed)}, New to follow: {len(to_follow)}")
            
            if not to_follow:
                job.status = 'completed'
                job.progress_percent = 100
                job.progress_message = 'Already following all artists'
                job.output_data = json.dumps({
                    'message': 'Already following all artists',
                    'total_artists': len(artists),
                    'already_following': len(followed)
                })
                job.completed_at = datetime.utcnow()
                update_job_progress(job, 100, "Complete!", "No new artists to follow")
                db.session.commit()
                return
            
            # Follow artists in batches
            update_job_progress(job, 65, f"Following {len(to_follow)} artists...", f"Starting to follow {len(to_follow)} new artists")
            followed_count = 0
            artist_list = list(to_follow)
            total_batches = (len(artist_list) + 49) // 50
            
            for i, batch_start in enumerate(range(0, len(artist_list), 50)):
                batch = artist_list[batch_start:batch_start + 50]
                try:
                    sp.user_follow_artists(batch)
                    followed_count += len(batch)
                    progress = 65 + int((i + 1) / total_batches * 30)
                    update_job_progress(job, progress, f"Following artists: {followed_count}/{len(to_follow)}", 
                                      f"Followed batch {i+1}/{total_batches}: {len(batch)} artists")
                    time.sleep(0.2)
                except Exception as e:
                    update_job_progress(job, progress, f"Following artists: {followed_count}/{len(to_follow)}", 
                                      f"Error following batch {i+1}: {str(e)}")
            
            job.status = 'completed'
            job.progress_percent = 100
            job.progress_message = f'Successfully followed {followed_count} artists'
            job.output_data = json.dumps({
                'followed': followed_count,
                'total_artists': len(artists),
                'already_following': len(followed),
                'new_follows': followed_count
            })
            job.completed_at = datetime.utcnow()
            update_job_progress(job, 100, "Complete!", f"Job completed successfully. Followed {followed_count} new artists.")
            db.session.commit()
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            job.status = 'failed'
            job.progress_percent = 0
            job.progress_message = f'Error: {str(e)}'
            job.output_data = json.dumps({'error': str(e)})
            job.execution_log = (job.execution_log or '') + f"\n[ERROR] {error_trace}"
            job.completed_at = datetime.utcnow()
            db.session.commit()


def find_instagram_task(user_id, job_id, limit=None, run_apify=False):
    """Find Instagram accounts for followed artists."""
    with app.app_context():
        user = User.query.get(user_id)
        job = Job.query.get(job_id)
        
        if not user or not job:
            return
        
        job.status = 'running'
        update_job_progress(job, 0, "Starting...", "Initializing Spotify connection")
        db.session.commit()
        
        try:
            sp = get_user_spotify_client(user)
            if not sp:
                raise Exception("Spotify not connected")
            
            # Get input data
            input_data = {}
            if job.input_data:
                try:
                    input_data = json.loads(job.input_data)
                except Exception:
                    pass
            
            limit = input_data.get('limit', limit)
            run_apify = input_data.get('run_apify', run_apify)
            
            # Get followed artists
            update_job_progress(job, 10, "Fetching followed artists...", "Getting list of followed artists from Spotify")
            artists = []
            after = None
            
            while True:
                results = sp.current_user_followed_artists(limit=50, after=after)
                items = results["artists"]["items"]
                if not items:
                    break
                
                for artist in items:
                    artists.append({
                        'name': artist['name'],
                        'id': artist['id']
                    })
                    
                    # Apply limit if specified
                    if limit and len(artists) >= limit:
                        break
                
                if limit and len(artists) >= limit:
                    break
                    
                if results["artists"]["next"]:
                    after = items[-1]["id"]
                else:
                    break
            
            # Search for Instagram profiles
            update_job_progress(job, 20, f"Searching for Instagram profiles...", f"Found {len(artists)} followed artists" + (f" (limited to {limit})" if limit else ""))
            
            results_list = []
            total_artists = len(artists)
            artist_names_list = []
            urls_list = []
            found_count = 0
            
            import re
            from urllib.parse import quote
            import random
            
            # Invalid Instagram paths that are not user profiles
            invalid_paths = ['accounts', 'web', 'about', 'blog', 'help', 'explore', 'direct', 'privacy', 'terms', 'jobs', 'developers', 'p', 'reels', 'explore', 'tags', 'stories']
            instagram_patterns = [
                r'https://www\.instagram\.com/([a-zA-Z0-9._]{1,30})/?',
                r'instagram\.com/([a-zA-Z0-9._]{1,30})/?',
                r'www\.instagram\.com/([a-zA-Z0-9._]{1,30})/?',
            ]
            
            def construct_instagram_urls(artist_name):
                """
                Generate likely Instagram profile URLs from artist name.
                Returns list of URL variations to try.
                """
                base = artist_name.lower().strip()
                
                # Remove common words like "the", "a", "an" from anywhere in the name (case-insensitive)
                # These are often omitted in Instagram usernames
                common_words = ['the ', ' a ', ' an ']
                base_without_common = base
                for word in common_words:
                    # Remove from anywhere in the string
                    base_without_common = base_without_common.replace(word, ' ')
                    # Also check if it's at the start
                    if base_without_common.startswith(word.strip() + ' '):
                        base_without_common = base_without_common[len(word.strip()) + 1:]
                    # Clean up extra spaces
                    base_without_common = ' '.join(base_without_common.split())
                
                # Also create version without "the" at start (for backward compatibility)
                if base.startswith('the '):
                    base_without_the_prefix = base[4:].strip()
                else:
                    base_without_the_prefix = base_without_common
                
                # Try various normalization patterns
                variations = [
                    # Original with spaces
                    base,                                    # "jeff the brotherhood" → "jeff the brotherhood"
                    base.replace(' ', ''),                   # "jeff the brotherhood" → "jeffthebrotherhood"
                    base.replace(' ', '.'),                  # "jeff the brotherhood" → "jeff.the.brotherhood"
                    base.replace(' ', '_'),                  # "jeff the brotherhood" → "jeff_the_brotherhood"
                    
                    # Without common words (removed from anywhere)
                    base_without_common,                     # "jeff the brotherhood" → "jeff brotherhood"
                    base_without_common.replace(' ', ''),   # "jeff the brotherhood" → "jeffbrotherhood"
                    base_without_common.replace(' ', '.'),  # "jeff the brotherhood" → "jeff.brotherhood"
                    base_without_common.replace(' ', '_'),  # "jeff the brotherhood" → "jeff_brotherhood"
                    
                    # Without "the" prefix only (backward compatibility)
                    base_without_the_prefix,                 # "the beatles" → "beatles"
                    base_without_the_prefix.replace(' ', ''), # "fleetwood mac" → "fleetwoodmac"
                    base_without_the_prefix.replace(' ', '.'), # "fleetwood mac" → "fleetwood.mac"
                    base_without_the_prefix.replace(' ', '_'), # "fleetwood mac" → "fleetwood_mac"
                ]
                
                # Remove duplicates while preserving order
                seen = set()
                unique_variations = []
                for var in variations:
                    if var and var not in seen:
                        seen.add(var)
                        unique_variations.append(var)
                
                urls = []
                for username in unique_variations:
                    # Remove invalid characters (keep alphanumeric, dots, underscores, hyphens)
                    username = ''.join(c for c in username if c.isalnum() or c in '._-')
                    # Instagram usernames must be 1-30 chars, at least 1 char
                    if len(username) >= 1 and len(username) <= 30:
                        urls.append(f'https://www.instagram.com/{username}/')
                
                return urls
            
            def get_instagram_profile_via_api(username):
                """
                Fetch Instagram profile using Instagram's internal API.
                Returns profile URL if found, None otherwise.
                """
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'x-ig-app-id': '936619743392459',  # Public Instagram web app ID
                    'Accept': 'application/json',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Origin': 'https://www.instagram.com',
                    'Referer': 'https://www.instagram.com/',
                }
                
                try:
                    # Instagram's internal API endpoint
                    url = f'https://www.instagram.com/api/v1/users/web_profile_info/'
                    params = {'username': username}
                    
                    response = requests.get(url, params=params, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('data', {}).get('user'):
                            verified_username = data['data']['user'].get('username')
                            if verified_username:
                                return f'https://www.instagram.com/{verified_username}/'
                    elif response.status_code == 404:
                        # User doesn't exist
                        return None
                    # Other status codes (403, 429, etc.) might indicate blocking/rate limiting
                except requests.exceptions.Timeout:
                    # Timeout - API might be slow or blocked
                    pass
                except requests.exceptions.RequestException:
                    # Network error or other request issue
                    pass
                except Exception as e:
                    # Other errors (JSON parsing, etc.)
                    pass
                
                return None
            
            def verify_instagram_url(instagram_url):
                """
                Check if an Instagram profile URL actually exists using HTTP requests.
                Returns (True, username) if the profile exists, (False, None) otherwise.
                """
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                }
                
                try:
                    # Extract username from URL
                    match = re.search(r'instagram\.com/([a-zA-Z0-9._]{1,30})/?', instagram_url)
                    if not match:
                        return False, None
                    
                    username = match.group(1)
                    
                    # Skip invalid paths
                    if username in invalid_paths:
                        return False, None
                    
                    # Use HEAD request first (lightweight)
                    try:
                        response = requests.head(instagram_url, headers=headers, timeout=10, allow_redirects=True)
                        if response.status_code == 200:
                            final_url = response.url
                            if 'instagram.com/' + username in final_url or 'instagram.com/' + username + '/' in final_url:
                                return True, username
                    except requests.exceptions.RequestException:
                        pass
                    
                    # Fallback to GET if HEAD fails
                    try:
                        response = requests.get(instagram_url, headers=headers, timeout=10, allow_redirects=True)
                        if response.status_code == 200:
                            final_url = response.url
                            match = re.search(r'instagram\.com/([a-zA-Z0-9._]{1,30})/?', final_url)
                            if match and match.group(1) == username:
                                return True, username
                            if username in final_url and 'login' not in final_url.lower():
                                return True, username
                    except requests.exceptions.RequestException:
                        pass
                    
                    return False, None
                except Exception as e:
                    return False, None
            
            def search_for_instagram(artist_name):
                """
                Find Instagram profile for an artist using multiple strategies (tiered approach).
                Returns Instagram profile URL or None.
                """
                strategy_used = None
                
                # Strategy 1: Construct likely URLs and verify them
                update_job_progress(job, job.progress_percent, job.progress_message,
                                  f"Strategy 1: Constructing likely Instagram URLs for '{artist_name}'...")
                
                instagram_urls = construct_instagram_urls(artist_name)
                update_job_progress(job, job.progress_percent, job.progress_message,
                                  f"Generated {len(instagram_urls)} URL variations to check")
                
                verified_count = 0
                for url in instagram_urls:
                    exists, username = verify_instagram_url(url)
                    verified_count += 1
                    if exists:
                        strategy_used = "URL construction + verification"
                        update_job_progress(job, job.progress_percent, job.progress_message,
                                          f"✓ Found via {strategy_used}: {url}\nUsername: {username}")
                        return url
                    # Delay between checks to avoid rate limiting (increased for API calls)
                    time.sleep(0.5)
                
                if verified_count > 0:
                    update_job_progress(job, job.progress_percent, job.progress_message,
                                      f"Checked {verified_count} URL variations, none verified as existing profiles")
                
                # Strategy 2: Wikipedia lookup (reliable, no API key needed)
                update_job_progress(job, job.progress_percent, job.progress_message,
                                  f"Strategy 2: Searching Wikipedia for '{artist_name}'...")
                
                try:
                    # Wikipedia API is free and doesn't require authentication
                    wiki_search_url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + quote(artist_name.replace(' ', '_'))
                    wiki_response = requests.get(wiki_search_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}, timeout=5)
                    
                    if wiki_response.status_code == 200:
                        # Try to get the full page HTML to find Instagram links in infobox
                        wiki_page_url = f"https://en.wikipedia.org/wiki/{quote(artist_name.replace(' ', '_'))}"
                        wiki_page_response = requests.get(wiki_page_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}, timeout=5)
                        
                        if wiki_page_response.status_code == 200:
                            page_html = wiki_page_response.text
                            # Look for Instagram URLs in the page (often in infobox or external links section)
                            for pattern in instagram_patterns:
                                matches = re.findall(pattern, page_html, re.IGNORECASE)
                                if matches:
                                    for username in matches:
                                        if username not in invalid_paths and len(username) > 1:
                                            # Verify the URL actually exists
                                            instagram_url = f'https://www.instagram.com/{username}/'
                                            exists, verified_username = verify_instagram_url(instagram_url)
                                            if exists:
                                                strategy_used = "Wikipedia"
                                                update_job_progress(job, job.progress_percent, job.progress_message,
                                                                  f"✓ Found via {strategy_used}: {instagram_url}\nUsername: {verified_username}")
                                                return instagram_url
                except Exception as wiki_error:
                    update_job_progress(job, job.progress_percent, job.progress_message,
                                      f"Wikipedia lookup failed: {str(wiki_error)[:100]}")
                
                # Strategy 3: Last.fm lookup (optional - requires LASTFM_API_KEY env var)
                lastfm_api_key = os.getenv('LASTFM_API_KEY')
                if lastfm_api_key:
                    update_job_progress(job, job.progress_percent, job.progress_message,
                                      f"Strategy 3: Searching Last.fm for '{artist_name}'...")
                    
                    try:
                        # Last.fm API requires an API key (get one free at https://www.last.fm/api/account/create)
                        lastfm_search_url = "https://ws.audioscrobbler.com/2.0/"
                        lastfm_params = {
                            'method': 'artist.search',
                            'artist': artist_name,
                            'api_key': lastfm_api_key,
                            'format': 'json',
                            'limit': 1
                        }
                        lastfm_response = requests.get(lastfm_search_url, params=lastfm_params, timeout=5)
                        
                        if lastfm_response.status_code == 200:
                            data = lastfm_response.json()
                            artists = data.get('results', {}).get('artistmatches', {}).get('artist', [])
                            if artists:
                                # Try to get artist info page which may have social links
                                artist_name_encoded = quote(artists[0].get('name', artist_name).replace(' ', '+'))
                                artist_info_url = f"https://www.last.fm/music/{artist_name_encoded}"
                                artist_page_response = requests.get(artist_info_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}, timeout=5)
                                
                                if artist_page_response.status_code == 200:
                                    page_html = artist_page_response.text
                                    # Look for Instagram URLs in the page
                                    for pattern in instagram_patterns:
                                        matches = re.findall(pattern, page_html, re.IGNORECASE)
                                        if matches:
                                            for username in matches:
                                                if username not in invalid_paths and len(username) > 1:
                                                    # Verify the URL actually exists
                                                    instagram_url = f'https://www.instagram.com/{username}/'
                                                    exists, verified_username = verify_instagram_url(instagram_url)
                                                    if exists:
                                                        strategy_used = "Last.fm"
                                                        update_job_progress(job, job.progress_percent, job.progress_message,
                                                                          f"✓ Found via {strategy_used}: {instagram_url}\nUsername: {verified_username}")
                                                        return instagram_url
                    except Exception as lastfm_error:
                        update_job_progress(job, job.progress_percent, job.progress_message,
                                          f"Last.fm lookup failed: {str(lastfm_error)[:100]}")
                else:
                    # Skip Last.fm if no API key configured
                    update_job_progress(job, job.progress_percent, job.progress_message,
                                      "Strategy 3: Skipping Last.fm (no LASTFM_API_KEY configured)")
                
                # Strategy 4: Genius.com lookup (optional - requires GENIUS_CLIENT_TOKEN env var)
                genius_token = os.getenv('GENIUS_CLIENT_TOKEN')
                if genius_token:
                    update_job_progress(job, job.progress_percent, job.progress_message,
                                      f"Strategy 4: Searching Genius for '{artist_name}'...")
                    
                    try:
                        # Genius API requires a client token (get one at https://genius.com/api-clients)
                        genius_search_url = "https://api.genius.com/search"
                        genius_headers = {
                            'Authorization': f'Bearer {genius_token}',
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                        }
                        genius_params = {'q': artist_name}
                        genius_response = requests.get(genius_search_url, params=genius_params, headers=genius_headers, timeout=5)
                        
                        if genius_response.status_code == 200:
                            data = genius_response.json()
                            hits = data.get('response', {}).get('hits', [])
                            
                            # Look for artist results
                            for hit in hits:
                                if hit.get('type') == 'artist':
                                    artist_result = hit.get('result', {})
                                    artist_url = artist_result.get('url')
                                    
                                    if artist_url:
                                        # Fetch the artist page to find Instagram links
                                        artist_page_response = requests.get(artist_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}, timeout=5)
                                        
                                        if artist_page_response.status_code == 200:
                                            page_html = artist_page_response.text
                                            # Look for Instagram URLs in the page
                                            for pattern in instagram_patterns:
                                                matches = re.findall(pattern, page_html, re.IGNORECASE)
                                                if matches:
                                                    for username in matches:
                                                        if username not in invalid_paths and len(username) > 1:
                                                            # Verify the URL actually exists
                                                            instagram_url = f'https://www.instagram.com/{username}/'
                                                            exists, verified_username = verify_instagram_url(instagram_url)
                                                            if exists:
                                                                strategy_used = "Genius"
                                                                update_job_progress(job, job.progress_percent, job.progress_message,
                                                                                  f"✓ Found via {strategy_used}: {instagram_url}\nUsername: {verified_username}")
                                                                return instagram_url
                                    break  # Only check first artist match
                    except Exception as genius_error:
                        update_job_progress(job, job.progress_percent, job.progress_message,
                                          f"Genius lookup failed: {str(genius_error)[:100]}")
                else:
                    # Skip Genius if no token configured
                    update_job_progress(job, job.progress_percent, job.progress_message,
                                      "Strategy 4: Skipping Genius (no GENIUS_CLIENT_TOKEN configured)")
                
                # Strategy 5: Try Instagram API with normalized usernames
                update_job_progress(job, job.progress_percent, job.progress_message,
                                  "Strategy 5: Trying Instagram API with username variations...")
                
                for url in instagram_urls[:5]:  # Limit to first 5 to avoid too many API calls
                    username = url.split('/')[-2]  # Extract username from URL
                    api_result = get_instagram_profile_via_api(username)
                    if api_result:
                        strategy_used = "Instagram API"
                        update_job_progress(job, job.progress_percent, job.progress_message,
                                          f"✓ Found via {strategy_used}: {api_result}\nUsername: {username}")
                        return api_result
                    time.sleep(0.5)  # Be respectful to Instagram API
                
                # Strategy 6: DuckDuckGo search (fallback, with improved parsing)
                update_job_progress(job, job.progress_percent, job.progress_message,
                                  f"Strategy 6: Searching DuckDuckGo for '{artist_name}' Instagram profile...")
                
                query = f'"{artist_name}" instagram profile'
                try:
                    from duckduckgo_search import DDGS
                    
                    with DDGS() as ddgs:
                        results = list(ddgs.text(query, max_results=10))
                        
                        if not results:
                            # Try without quotes
                            query_no_quotes = f'{artist_name} instagram profile'
                            results = list(ddgs.text(query_no_quotes, max_results=10))
                        
                        if results:
                            update_job_progress(job, job.progress_percent, job.progress_message,
                                              f"DuckDuckGo returned {len(results)} results, parsing for Instagram URLs...")
                            
                            for result in results:
                                url = result.get('href', '')
                                body = result.get('body', '')
                                title = result.get('title', '')
                                
                                # Check if the result URL itself is an Instagram profile
                                if 'instagram.com' in url:
                                    for pattern in instagram_patterns:
                                        matches = re.findall(pattern, url)
                                        if matches:
                                            username = matches[0]
                                            # Allow dots in usernames (they're valid)
                                            if username not in invalid_paths and len(username) > 1:
                                                # Verify the URL actually exists
                                                exists, verified_username = verify_instagram_url(f'https://www.instagram.com/{username}/')
                                                if exists:
                                                    strategy_used = "DuckDuckGo search"
                                                    instagram_url = f'https://www.instagram.com/{verified_username}/'
                                                    update_job_progress(job, job.progress_percent, job.progress_message,
                                                                      f"✓ Found via {strategy_used}: {instagram_url}\nUsername: {verified_username}")
                                                    return instagram_url
                                
                                # Check title and body text for Instagram URLs
                                text_to_search = title + ' ' + body + ' ' + url
                                for pattern in instagram_patterns:
                                    matches = re.findall(pattern, text_to_search, re.IGNORECASE)
                                    if matches:
                                        for username in matches:
                                            if username not in invalid_paths and len(username) > 1:
                                                # Verify the URL actually exists
                                                exists, verified_username = verify_instagram_url(f'https://www.instagram.com/{username}/')
                                                if exists:
                                                    strategy_used = "DuckDuckGo search (in text)"
                                                    instagram_url = f'https://www.instagram.com/{verified_username}/'
                                                    update_job_progress(job, job.progress_percent, job.progress_message,
                                                                      f"✓ Found via {strategy_used}: {instagram_url}\nUsername: {verified_username}")
                                                    return instagram_url
                        else:
                            update_job_progress(job, job.progress_percent, job.progress_message,
                                              "DuckDuckGo returned 0 results")
                except Exception as ddg_error:
                    update_job_progress(job, job.progress_percent, job.progress_message,
                                      f"DuckDuckGo search failed: {str(ddg_error)}")
                
                # Strategy 7: Google search (last resort) - skip if rate limited
                update_job_progress(job, job.progress_percent, job.progress_message,
                                  f"Strategy 7: Searching Google for '{artist_name}' Instagram profile...")
                
                try:
                    from googlesearch import search
                    
                    result_count = 0
                    for url in search(query, num_results=10):
                        result_count += 1
                        if result_count > 10:
                            break
                        
                        # Check if the URL itself is an Instagram profile
                        if 'instagram.com' in url:
                            for pattern in instagram_patterns:
                                matches = re.findall(pattern, url)
                                if matches:
                                    username = matches[0]
                                    if username not in invalid_paths and len(username) > 1:
                                        # Verify the URL actually exists
                                        exists, verified_username = verify_instagram_url(f'https://www.instagram.com/{username}/')
                                        if exists:
                                            strategy_used = "Google search"
                                            instagram_url = f'https://www.instagram.com/{verified_username}/'
                                            update_job_progress(job, job.progress_percent, job.progress_message,
                                                              f"✓ Found via {strategy_used}: {instagram_url}\nUsername: {verified_username}")
                                            return instagram_url
                        
                        # Small delay to be respectful
                        if result_count < 10:
                            time.sleep(0.5)
                    
                    if result_count == 0:
                        update_job_progress(job, job.progress_percent, job.progress_message,
                                          "Google search returned 0 results")
                except Exception as google_error:
                    error_str = str(google_error)
                    # Check if it's a rate limit error
                    if '429' in error_str or 'Too Many Requests' in error_str:
                        update_job_progress(job, job.progress_percent, job.progress_message,
                                          "Google search rate limited (429) - skipping to avoid further blocks")
                    else:
                        update_job_progress(job, job.progress_percent, job.progress_message,
                                          f"Google search error: {error_str[:100]}")
                
                # No profile found with any strategy
                update_job_progress(job, job.progress_percent, job.progress_message,
                                  f"✗ No Instagram profile found for '{artist_name}' after trying all strategies")
                return None
            
            # Search for each artist's Instagram profile
            for idx, artist in enumerate(artists):
                artist_name = artist['name']
                artist_names_list.append(artist_name)
                
                # Search DuckDuckGo
                progress = 20 + int((idx + 1) / total_artists * 60)  # Use 60% of progress for searching
                update_job_progress(job, progress, 
                                  f"Searching {idx + 1}/{total_artists}: {artist_name}", 
                                  f"Searching for {artist_name} Instagram profile...")
                
                instagram_url = search_for_instagram(artist_name)
                
                if instagram_url:
                    urls_list.append(instagram_url)
                    found_count += 1
                    results_list.append({
                        'artist': artist_name,
                        'instagram_handle': instagram_url.replace('https://www.instagram.com/', '').rstrip('/'),
                        'instagram_url': instagram_url,
                        'found': True,
                        'note': 'Found via search'
                    })
                    update_job_progress(job, progress, 
                                      f"Found {idx + 1}/{total_artists}: {artist_name}", 
                                      f"Found Instagram: {instagram_url}")
                else:
                    results_list.append({
                        'artist': artist_name,
                        'instagram_handle': None,
                        'instagram_url': None,
                        'found': False,
                        'note': 'Not found via search'
                    })
                    update_job_progress(job, progress, 
                                      f"Searched {idx + 1}/{total_artists}: {artist_name}", 
                                      f"No Instagram profile found for {artist_name}")
                
                # Rate limiting - be respectful to Google
                time.sleep(1 + random.uniform(0, 1))
            
            job.progress_percent = 80
            job.progress_message = f'Found {found_count} Instagram profiles from {total_artists} artists'
            
            output_data = {
                'artists_checked': total_artists,
                'found_count': found_count,
                'total_urls': len(urls_list),
                'results': results_list,
                'note': f'Found {found_count} Instagram profiles via search'
            }
            
            # If user wants to run Apify and has credentials, trigger it
            # Pass URLs found via search to Apify
            # Note: Apify will only run if URLs are found
            if run_apify:
                if not urls_list:
                    update_job_progress(job, 100, "Complete!", 
                                      f"Job completed. Found 0 Instagram profiles from {total_artists} artists. Apify cannot run without URLs.")
                    output_data['apify_note'] = f"Apify actor was not run because no Instagram URLs were found (searched {total_artists} artists, found {found_count} profiles)."
                elif urls_list:
                    # Get Apify config from environment (server-side, not user-specific)
                    apify_api_token = os.getenv('APIFY_API_TOKEN')
                    # Use actor name format (username~actor-name) for stable reference - API uses tilde instead of slash
                    apify_actor_id = os.getenv('APIFY_ACTOR_ID', 'fulfilling_relish~spotify-artists-instagram-follow')
                    
                    # Get Instagram credentials from user settings
                    instagram_session_id = getattr(user, 'instagram_session_id', None)
                    instagram_username = user.instagram_username
                    instagram_password_to_use = user.instagram_password
                    
                    # Session ID is preferred, but username+password works as fallback
                    has_valid_creds = instagram_session_id or (instagram_username and instagram_password_to_use)
                    
                    if not apify_api_token:
                        output_data['apify_error'] = "Apify API token not configured. Please contact administrator."
                    elif not has_valid_creds:
                        output_data['apify_error'] = "Missing Instagram credentials. Please add your Session ID (recommended) or username/password in Settings."
                    else:
                        update_job_progress(job, 85, "Starting Apify actor...", f"Starting Apify actor to follow {len(urls_list)} Instagram profiles found via search.")
                        db.session.commit()
                        
                        try:
                            apify_input = {
                                "urls": urls_list,  # URLs found via search
                                "artist_names": [],  # Don't search Instagram - we already found URLs
                                "instagram_session_id": instagram_session_id or "",
                                "instagram_username": instagram_username or "",
                                "instagram_password": instagram_password_to_use or "",
                                "delay_min": 30,
                                "delay_max": 90,
                                "max_follows": min(40, len(urls_list)),  # Limit to number of URLs found
                                "headless": False
                            }
                            
                            # Validate input before sending - URLs should already be validated above
                            if not apify_input["urls"]:
                                output_data['apify_error'] = f"No Instagram URLs found. Searched {total_artists} artists, found {found_count} profiles."
                                update_job_progress(job, 100, "Complete!", 
                                                  f"No Instagram profiles found for {total_artists} artists. Apify actor cannot run without URLs.")
                                job.status = 'completed'
                                job.output_data = json.dumps(output_data, indent=2)
                                job.completed_at = datetime.utcnow()
                                db.session.commit()
                            else:
                                # Call Apify API to start actor run
                                # First, get the latest build to ensure we use the most recent code
                                latest_build_tag = None
                                try:
                                    # Use desc=true to get builds in descending order (newest first)
                                    builds_url = f"https://api.apify.com/v2/acts/{apify_actor_id}/builds?limit=1&desc=true"
                                    builds_response = requests.get(builds_url, headers={"Authorization": f"Bearer {apify_api_token}"}, timeout=5)
                                    if builds_response.status_code == 200:
                                        builds_data = builds_response.json()
                                        if builds_data.get('data', {}).get('items'):
                                            # Get the first (most recent) build
                                            latest_build = builds_data['data']['items'][0]
                                            # Use build number (like "1.0.4") as tag, not build ID
                                            latest_build_tag = latest_build.get('buildNumber')
                                            latest_build_id = latest_build.get('id')
                                            update_job_progress(job, 96, "Calling Apify API...", 
                                                              f"Using latest build: {latest_build_tag} (ID: {latest_build_id})")
                                            db.session.commit()
                                except Exception as e:
                                    # If we can't get the latest build, continue with default
                                    update_job_progress(job, 96, "Calling Apify API...", 
                                                      f"Could not fetch latest build, using default: {str(e)}")
                                    db.session.commit()
                                
                                # Apify API expects input in a specific format
                                # Use build number (tag) as a query parameter (not build ID)
                                apify_url = f"https://api.apify.com/v2/acts/{apify_actor_id}/runs"
                                if latest_build_tag:
                                    apify_url += f"?build={latest_build_tag}"
                                    update_job_progress(job, 96, "Calling Apify API...", 
                                                      f"URL: {apify_url[:100]}... (using build tag {latest_build_tag})")
                                else:
                                    update_job_progress(job, 96, "Calling Apify API...", 
                                                      f"URL: {apify_url} (no build specified - will use default)")
                                db.session.commit()
                                
                                headers = {
                                    "Authorization": f"Bearer {apify_api_token}",
                                    "Content-Type": "application/json"
                                }
                                
                                update_job_progress(job, 96, "Calling Apify API...", 
                                                  f"Calling Apify API with {len(urls_list)} Instagram URLs")
                                db.session.commit()
                                
                                # Log what we're sending (without password)
                                debug_input = {k: v for k, v in apify_input.items() if k not in ['instagram_password', 'instagram_session_id']}
                                debug_input['instagram_password'] = '***hidden***'
                                debug_input['instagram_session_id'] = '***hidden***' if apify_input.get('instagram_session_id') else ''
                                update_job_progress(job, 96, "Calling Apify API...", 
                                                  f"Sending input: {json.dumps(debug_input, indent=2)[:500]}")
                                db.session.commit()
                                
                                # Apify API v2: Send input in request body under "input" key
                                request_body = {"input": apify_input}
                                response = requests.post(apify_url, json=request_body, headers=headers, timeout=15)
                                
                                if response.status_code in [200, 201]:
                                    apify_run = response.json()
                                    output_data['apify_run_id'] = apify_run.get('data', {}).get('id')
                                    output_data['apify_run_url'] = f"https://console.apify.com/actors/runs/{output_data['apify_run_id']}"
                                    job.progress_message = f'Apify actor started! Following {len(urls_list)} Instagram profiles.'
                                    update_job_progress(job, 100, "Complete!", 
                                                      f"Apify actor run started! It will follow {len(urls_list)} Instagram profiles. View progress: {output_data['apify_run_url']}")
                                else:
                                    error_msg = response.text[:200]  # Limit error message length
                                    output_data['apify_error'] = f"Failed to start Apify actor (HTTP {response.status_code}): {error_msg}"
                                    update_job_progress(job, 100, "Complete!", 
                                                      f"Prepared {len(urls_list)} Instagram URLs, but failed to start Apify actor: {error_msg}")
                        except requests.exceptions.Timeout:
                            output_data['apify_error'] = "Apify API call timed out after 15 seconds"
                            update_job_progress(job, 100, "Complete!", 
                                              f"Prepared {len(urls_list)} Instagram URLs, but Apify API call timed out")
                        except Exception as e:
                            import traceback
                            error_trace = traceback.format_exc()[:500]  # Limit traceback length
                            output_data['apify_error'] = f"Error starting Apify actor: {str(e)}"
                            update_job_progress(job, 100, "Complete!", 
                                              f"Prepared {len(urls_list)} Instagram URLs, but error starting Apify actor: {str(e)}")
            
            # Only set status to completed if Apify wasn't run (or if it failed)
            if not run_apify or not urls_list:
                job.status = 'completed'
                job.output_data = json.dumps(output_data, indent=2)
                job.completed_at = datetime.utcnow()
                if not run_apify:
                    update_job_progress(job, 100, "Complete!",
                                      f"Job completed. Found {found_count} Instagram profiles from {total_artists} artists. Enable 'Automatically run Apify actor' to follow the accounts.")
                else:
                    update_job_progress(job, 100, "Complete!",
                                      f"Job completed. Found {found_count} Instagram profiles from {total_artists} artists, but no URLs to send to Apify.")
                db.session.commit()
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            job.status = 'failed'
            job.progress_percent = 0
            job.progress_message = f'Error: {str(e)}'
            job.output_data = json.dumps({'error': str(e)})
            job.execution_log = (job.execution_log or '') + f"\n[ERROR] {error_trace}"
            job.completed_at = datetime.utcnow()
            db.session.commit()


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in miles using Haversine formula."""
    import math
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return c * 3959  # Earth radius in miles


def geocode_location(location_string, job=None):
    """Geocode a location string to get latitude/longitude."""
    if not location_string or not location_string.strip():
        return None, None
    
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": location_string,
            "format": "json",
            "limit": 1,
        }
        headers = {
            "User-Agent": "GrooveGremlin/1.0"
        }
        response = requests.get(url, params=params, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data:
                lat = float(data[0]["lat"])
                lon = float(data[0]["lon"])
                return lat, lon
    except Exception as e:
        if job:
            update_job_progress(job, job.progress_percent or 0, job.progress_message or '', 
                              f"Geocoding error: {str(e)}")
    
    return None, None


def find_concerts_task(user_id, job_id, location=None, radius_miles=None, months_ahead=3):
    """Find concerts for followed artists."""
    with app.app_context():
        user = User.query.get(user_id)
        job = Job.query.get(job_id)
        
        if not user or not job:
            return
        
        job.status = 'running'
        update_job_progress(job, 0, "Starting...", "Initializing concert search")
        db.session.commit()
        
        try:
            sp = get_user_spotify_client(user)
            if not sp:
                raise Exception("Spotify not connected")
            
            # Geocode location if provided
            user_lat, user_lon = None, None
            if location and location.strip():
                update_job_progress(job, 10, f"Geocoding location: {location}", f"Looking up coordinates for: {location}")
                user_lat, user_lon = geocode_location(location, job)
                if user_lat and user_lon:
                    update_job_progress(job, 15, f"Location found: {user_lat:.4f}, {user_lon:.4f}", 
                                      f"Geocoded location to coordinates: {user_lat:.4f}, {user_lon:.4f}")
                else:
                    update_job_progress(job, 15, "Location not found, searching all locations", 
                                      f"Could not geocode '{location}', will search all locations")
            
            # Get followed artists
            update_job_progress(job, 20, "Fetching followed artists...", "Getting list of followed artists from Spotify")
            artists = []
            after = None
            total_artists = None
            
            while True:
                results = sp.current_user_followed_artists(limit=50, after=after)
                items = results["artists"]["items"]
                if not items:
                    break
                for artist in items:
                    artists.append({
                        'name': artist['name'],
                        'id': artist['id']
                    })
                if results["artists"]["next"]:
                    after = items[-1]["id"]
                else:
                    break
            
            update_job_progress(job, 30, f"Found {len(artists)} followed artists", f"Found {len(artists)} artists to search")
            
            # Search Bandsintown for events
            update_job_progress(job, 35, "Searching for concerts...", "Querying Bandsintown API for events")
            all_events = []
            cutoff_date = datetime.utcnow() + timedelta(days=months_ahead * 30)
            
            for idx, artist in enumerate(artists):
                try:
                    encoded_name = requests.utils.quote(artist['name'])
                    url = f"https://rest.bandsintown.com/artists/{encoded_name}/events"
                    params = {"app_id": "spotify_concert_finder", "date": "upcoming"}
                    response = requests.get(url, params=params, timeout=5)
                    
                    if response.status_code == 200:
                        artist_events = response.json()
                        if isinstance(artist_events, list):
                            for event in artist_events:
                                # Filter by date
                                try:
                                    event_date = datetime.fromisoformat(event["datetime"].replace("Z", "+00:00"))
                                    if event_date.replace(tzinfo=None) <= cutoff_date:
                                        all_events.append({
                                            'artist': artist['name'],
                                            'event': event
                                        })
                                except (KeyError, ValueError):
                                    # Include events with unparseable dates
                                    all_events.append({
                                        'artist': artist['name'],
                                        'event': event
                                    })
                    
                    progress = 35 + int((idx + 1) / len(artists) * 50)
                    update_job_progress(job, progress, f"Searching artists: {idx + 1}/{len(artists)}", 
                                      f"Searched {artist['name']}: found {len([e for e in all_events if e['artist'] == artist['name']])} events")
                    time.sleep(0.3)
                except Exception as e:
                    update_job_progress(job, 35 + int((idx + 1) / len(artists) * 50), 
                                      f"Searching artists: {idx + 1}/{len(artists)}", 
                                      f"Error searching {artist['name']}: {str(e)}")
            
            # Filter by location/radius if provided
            filtered_events = all_events
            if user_lat and user_lon and radius_miles and radius_miles > 0:
                update_job_progress(job, 85, f"Filtering by location (radius: {radius_miles} miles)...", 
                                  f"Filtering {len(all_events)} events within {radius_miles} miles")
                filtered_events = []
                for item in all_events:
                    event = item['event']
                    venue = event.get("venue", {})
                    venue_lat = venue.get("latitude")
                    venue_lon = venue.get("longitude")
                    
                    if venue_lat is not None and venue_lon is not None:
                        try:
                            distance = haversine_distance(user_lat, user_lon, float(venue_lat), float(venue_lon))
                            if distance <= radius_miles:
                                filtered_events.append(item)
                        except (ValueError, TypeError):
                            pass
                    else:
                        # No coordinates, include if location string matches
                        venue_city = venue.get("city", "").lower()
                        if location and location.lower() in venue_city:
                            filtered_events.append(item)
            elif location and location.strip() and (not radius_miles or radius_miles == 0):
                # String matching only
                update_job_progress(job, 85, f"Filtering by location: {location}...", 
                                  f"Filtering {len(all_events)} events by location string")
                location_lower = location.lower()
                filtered_events = []
                for item in all_events:
                    event = item['event']
                    venue = event.get("venue", {})
                    venue_city = venue.get("city", "").lower()
                    venue_region = venue.get("region", "").lower()
                    venue_country = venue.get("country", "").lower()
                    
                    if (location_lower in venue_city or 
                        location_lower in venue_region or 
                        location_lower in venue_country):
                        filtered_events.append(item)
            
            job.status = 'completed'
            job.progress_percent = 100
            job.progress_message = f'Found {len(filtered_events)} concerts'
            job.output_data = json.dumps({
                'events_found': len(filtered_events),
                'total_events': len(all_events),
                'location': location,
                'radius_miles': radius_miles,
                'months_ahead': months_ahead,
                'events': filtered_events
            })
            job.completed_at = datetime.utcnow()
            update_job_progress(job, 100, "Complete!", 
                              f"Job completed. Found {len(filtered_events)} concerts (from {len(all_events)} total events)")
            db.session.commit()
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            job.status = 'failed'
            job.progress_percent = 0
            job.progress_message = f'Error: {str(e)}'
            job.output_data = json.dumps({'error': str(e)})
            job.execution_log = (job.execution_log or '') + f"\n[ERROR] {error_trace}"
            job.completed_at = datetime.utcnow()
            db.session.commit()


def randomize_playlists_task(user_id, job_id, playlist_ids=None):
    """Randomize playlist order. If playlist_ids is provided, only randomize those playlists."""
    with app.app_context():
        user = User.query.get(user_id)
        job = Job.query.get(job_id)
        
        if not user or not job:
            return
        
        job.status = 'running'
        update_job_progress(job, 0, "Starting...", "Initializing Spotify connection")
        db.session.commit()
        
        try:
            sp = get_user_spotify_client(user)
            if not sp:
                raise Exception("Spotify not connected")
            
            # If specific playlists provided, use those; otherwise get all
            if playlist_ids and len(playlist_ids) > 0:
                update_job_progress(job, 10, f"Randomizing {len(playlist_ids)} selected playlists...", f"Processing {len(playlist_ids)} selected playlists")
                playlists = playlist_ids
            else:
                update_job_progress(job, 10, "Fetching playlists...", "Connected to Spotify API")
                
                # Get user's playlists
                update_job_progress(job, 15, "Fetching your playlists...", "Getting list of user playlists")
                playlists = []
                offset = 0
                while True:
                    results = sp.current_user_playlists(limit=50, offset=offset)
                    if not results["items"]:
                        break
                    for playlist in results["items"]:
                        if playlist["owner"]["id"] == user.spotify_user_id:
                            playlists.append(playlist["id"])
                    offset += 50
                    if offset >= results["total"]:
                        break
                
                update_job_progress(job, 25, f"Found {len(playlists)} playlists", f"Found {len(playlists)} playlists to randomize")
            
            randomized_count = 0
            for idx, playlist_id in enumerate(playlists):
                try:
                    # Get tracks
                    tracks = []
                    offset = 0
                    while True:
                        results = sp.playlist_items(playlist_id, limit=100, offset=offset)
                        if not results["items"]:
                            break
                        for item in results["items"]:
                            track = item.get("track")
                            if track and track.get("uri") and track.get("uri").startswith("spotify:track:"):
                                if not track.get("is_local"):
                                    tracks.append(track["uri"])
                        offset += 100
                        if not results.get("next"):
                            break
                    
                    if len(tracks) >= 2:
                        # Shuffle
                        random.shuffle(tracks)
                        # Replace
                        if len(tracks) <= 100:
                            sp.playlist_replace_items(playlist_id, tracks)
                        else:
                            sp.playlist_replace_items(playlist_id, [])
                            for i in range(0, len(tracks), 100):
                                sp.playlist_add_items(playlist_id, tracks[i:i+100])
                        randomized_count += 1
                        
                        progress = 25 + int((idx + 1) / len(playlists) * 70)
                        update_job_progress(job, progress, f"Randomizing playlists: {idx + 1}/{len(playlists)}", 
                                          f"Randomized playlist {idx + 1}/{len(playlists)}: {len(tracks)} tracks shuffled")
                        time.sleep(0.2)
                    else:
                        update_job_progress(job, 25 + int((idx + 1) / len(playlists) * 70), 
                                          f"Processing playlists: {idx + 1}/{len(playlists)}", 
                                          f"Skipped playlist {idx + 1}/{len(playlists)}: Not enough tracks (< 2)")
                except Exception as e:
                    update_job_progress(job, 25 + int((idx + 1) / len(playlists) * 70), 
                                      f"Processing playlists: {idx + 1}/{len(playlists)}", 
                                      f"Error randomizing playlist {idx + 1}/{len(playlists)}: {str(e)}")
            
            job.status = 'completed'
            job.progress_percent = 100
            job.progress_message = f'Successfully randomized {randomized_count} playlists'
            job.output_data = json.dumps({
                'playlists_randomized': randomized_count,
                'total_playlists': len(playlists)
            })
            job.completed_at = datetime.utcnow()
            update_job_progress(job, 100, "Complete!", f"Job completed successfully. Randomized {randomized_count} out of {len(playlists)} playlists.")
            db.session.commit()
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            job.status = 'failed'
            job.progress_percent = 0
            job.progress_message = f'Error: {str(e)}'
            job.output_data = json.dumps({'error': str(e)})
            job.execution_log = (job.execution_log or '') + f"\n[ERROR] {error_trace}"
            job.completed_at = datetime.utcnow()
            db.session.commit()
