# Instagram Feature Process Outline

## Overview
The "Find Instagram Accounts" feature searches for Instagram profiles of artists you follow on Spotify, and optionally automatically follows them using the Apify actor.

## Step-by-Step Process

### 1. User Initiates Job
- User navigates to the "Find Instagram" tab in the Features page
- User can optionally set a limit on the number of artists to search (defaults to all)
- User can toggle "Automatically run Apify actor" (defaults to checked)
- User clicks "Find Instagram Accounts" button

### 2. Job Creation (Backend)
- Flask route `/jobs/find-instagram` receives POST request
- Creates a new `Job` record in database with:
  - `job_type`: "find_instagram"
  - `status`: "pending"
  - `user_id`: current user
- Enqueues `find_instagram_task` to Redis queue with:
  - `user_id`
  - `job_id`
  - `limit` (optional, number of artists to search)
  - `run_apify` (boolean, whether to automatically run Apify)

### 3. Worker Task Execution

#### 3.1 Initialize Spotify Connection
- Loads user's Spotify access token from database
- Creates Spotipy client with user's token
- Refreshes token if expired

#### 3.2 Get Followed Artists
- Calls `sp.current_user_followed_artists(limit=50)` to get first page
- Paginates through all followed artists if needed
- Applies limit if specified by user
- Returns list of artist objects with `name` and `id`

#### 3.3 Search for Instagram Profiles (Tiered Approach)
For each artist, the system uses a **tiered strategy** to find Instagram profiles, trying multiple methods in order of reliability:

**3.3.1 Strategy 1: URL Construction + Verification (Most Reliable)**
- Generates likely Instagram profile URLs from artist name using multiple normalization patterns:
  - Original name: `"Fleetwood Mac"` → `fleetwoodmac`, `fleetwood.mac`, `fleetwood_mac`
  - Without "The" prefix: `"The Beatles"` → `beatles`, `thebeatles`
  - Various separators: spaces removed, replaced with dots/underscores
- For each generated URL:
  - Uses `HEAD` request to verify the profile actually exists
  - Checks response status code (200 = exists, 404 = doesn't exist)
  - Validates final redirect URL to ensure it's a real profile
  - Returns first verified profile URL found
- **Advantages**: Fast, reliable, no external dependencies, respects rate limits

**3.3.2 Strategy 2: Instagram Internal API**
- If URL construction doesn't find a match, tries Instagram's internal REST API
- Uses normalized usernames from Strategy 1 (limited to first 5 to avoid rate limits)
- Calls `https://i.instagram.com/api/v1/users/web_profile_info/` with proper headers
- Includes Instagram web app ID (`x-ig-app-id: 936619743392459`)
- Returns verified profile URL if API confirms username exists
- **Advantages**: Direct API confirmation, returns verified usernames
- **Limitations**: May be rate-limited or blocked by Instagram

**3.3.3 Strategy 3: DuckDuckGo Search (Fallback)**
- Only runs if previous strategies fail
- Constructs query: `"<artist name>" instagram profile`
- Uses `duckduckgo_search.DDGS()` to search
- Gets up to 10 results
- If 0 results, tries query without quotes
- For each result:
  - Checks if result URL is an Instagram profile URL
  - Checks title and body text for Instagram URLs
  - Extracts username using regex patterns
  - **Verifies URL exists** using HEAD request (improved from previous version)
  - Allows dots in usernames (they're valid in Instagram)
  - Returns first verified Instagram URL found

**3.3.4 Strategy 4: Google Search (Last Resort)**
- Only runs if all previous strategies fail
- Uses `googlesearch.search()` to search Google
- Gets up to 10 results
- Checks each URL for Instagram profile patterns
- **Verifies URL exists** using HEAD request before returning
- Returns first verified Instagram URL found

**3.3.5 Result Tracking**
- If Instagram URL found:
  - Adds to `urls_list`
  - Records in `results_list` with `found: True` and strategy used
  - Updates job progress with strategy that found it
- If not found:
  - Records in `results_list` with `found: False`
  - Updates job progress indicating all strategies were tried

#### 3.4 Apify Actor Execution (Optional)
**Prerequisites:**
- `run_apify` must be `True`
- `urls_list` must not be empty
- User must have Instagram credentials in Settings
- Server must have `APIFY_API_TOKEN` and `APIFY_ACTOR_ID` configured

**If Apify should run:**
1. Get Apify configuration:
   - `APIFY_API_TOKEN` from environment
   - `APIFY_ACTOR_ID` from environment (defaults to `fulfilling_relish~spotify-artists-instagram-follow`)
   - Instagram username and password from user settings
   - Decrypts Instagram password using `check_password_hash`

2. Get latest Apify build:
   - Calls `GET /v2/acts/{actorId}/builds?limit=1&desc=true`
   - Extracts `buildNumber` (e.g., "1.0.4")
   - Uses this to ensure latest code is used

3. Prepare Apify input:
   ```json
   {
     "urls": ["https://www.instagram.com/username1/", ...],
     "artist_names": [],
     "instagram_username": "user's_instagram_username",
     "instagram_password": "decrypted_password",
     "delay_min": 2,
     "delay_max": 4,
     "max_follows": min(40, len(urls_list)),
     "headless": false
   }
   ```

4. Start Apify run:
   - Calls `POST /v2/acts/{actorId}/runs?build={buildNumber}`
   - Sends input wrapped in `{"input": {...}}`
   - Gets back run ID
   - Updates job progress with Apify run ID

**If Apify should not run (no URLs found):**
- Updates job with message explaining why Apify didn't run
- Sets job status to "completed"

#### 3.5 Job Completion
- Updates job with final results:
  - `status`: "completed" or "failed"
  - `output_data`: JSON with:
    - `artists_checked`: total number of artists searched
    - `found_count`: number of Instagram profiles found
    - `total_urls`: number of URLs in list
    - `results`: array of results for each artist
    - `note`: summary message
    - `apify_note`: message about Apify execution (if applicable)
    - `apify_run_id`: Apify run ID (if Apify was started)
    - `apify_error`: error message (if Apify failed)
- Sets `completed_at` timestamp

### 4. Apify Actor Execution (Separate Process)
**Note:** This runs independently on Apify's infrastructure after the web app starts it.

1. **Login to Instagram:**
   - Navigates to `https://www.instagram.com/accounts/login/`
   - Enters username and password
   - Handles 2FA if required
   - Waits for successful login

2. **Follow Instagram Profiles:**
   - For each URL in the `urls` list:
     - Navigates to the Instagram profile URL
     - Checks if already following
     - Clicks "Follow" button if not following
     - Waits random delay (2-4 seconds) between follows
     - Respects `max_follows` limit
   - Logs results (successful, already following, failed)

3. **Complete:**
   - Outputs summary of follows
   - Exits with success status

### 5. User Views Results
- User can view job status on Features page
- User can click "View" to see detailed job page with:
  - Progress bar
  - Execution log
  - Results summary
  - Download link for full results JSON
- If Apify was run, user can check Apify dashboard for follow results

## Data Flow

```
User Input
  ↓
Flask Route (/jobs/find-instagram)
  ↓
Job Created in Database
  ↓
Redis Queue (find_instagram_task)
  ↓
Worker Process
  ├─→ Spotify API (get followed artists)
  ├─→ DuckDuckGo/Google Search (find Instagram profiles)
  └─→ Apify API (start actor run) [if enabled]
       ↓
       Apify Infrastructure
       ├─→ Instagram Login
       └─→ Follow Profiles
```

## Key Components

### Frontend
- **Template**: `webapp/templates/features/find_instagram.html`
- **JavaScript**: Handles form submission, job status polling, job cancellation

### Backend
- **Route**: `webapp/app.py` - `/jobs/find-instagram` (POST)
- **Worker**: `webapp/workers.py` - `find_instagram_task()`
- **Search Function**: `webapp/workers.py` - `search_for_instagram()`

### External Services
- **Spotify API**: Get followed artists
- **Instagram Internal API**: Direct profile lookup (Strategy 2)
- **Instagram Web**: URL verification via HEAD requests (Strategy 1)
- **DuckDuckGo Search**: Fallback search engine (Strategy 3)
- **Google Search**: Last resort search engine (Strategy 4)
- **Apify Platform**: Instagram automation actor

## Error Handling

1. **Spotify Connection Issues**: Job marked as failed, error logged
2. **URL Verification Failures**: Silently continues to next URL variation or strategy
3. **Instagram API Rate Limiting**: Falls back to next strategy (expected behavior)
4. **Search Engine Failures**: Falls back to alternative search engine or marks as not found
5. **No Instagram Profiles Found**: Job completes successfully with 0 found count (all strategies tried)
6. **Apify Configuration Missing**: Error logged, job completes without Apify
7. **Apify API Errors**: Error logged, job completes with error message
8. **Instagram Login Failures**: Handled by Apify actor, logged in Apify dashboard

## Rate Limiting

- **URL Verification (Strategy 1)**: 0.3 second delay between HEAD requests
- **Instagram API (Strategy 2)**: 0.5 second delay between API calls, limited to 5 attempts per artist
- **DuckDuckGo/Google (Strategies 3-4)**: 0.5-1 second delay between searches
- **Between Artists**: 1-2 second random delay to be respectful
- **Apify Actor**: 2-4 second random delay between follows
- **Max Follows**: Limited to 40 per Apify run (configurable)

## Security

- Instagram passwords are hashed using `werkzeug.security.generate_password_hash`
- Passwords are decrypted only when needed for Apify
- Apify API token and actor ID are server-side environment variables
- User credentials are never exposed in frontend
