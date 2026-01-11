# Spotify Tools

A collection of scripts to enhance your Spotify experience.

## Quick Start

Run the main menu to access all utilities:

```bash
python spotify_tools.py
```

Or run individual scripts directly:

```bash
python follow_artists.py
python find_concerts.py
python randomize_playlists.py
```

## Scripts

| Script | Description |
|--------|-------------|
| `spotify_tools.py` | **Main menu** - Access all utilities from one place |
| `follow_artists.py` | Automatically follow all artists from your liked/saved tracks |
| `find_concerts.py` | Find upcoming concerts for artists you follow |
| `randomize_playlists.py` | Randomize the order of tracks in all your playlists |
| `find_instagram_accounts.py` | Find Instagram accounts for artists you follow |
| `webapp/` | **Web application** - Browser-based interface with user accounts |

## Web Application

A full web application is available in the `webapp/` directory that provides:

- ✅ User accounts and authentication
- ✅ Spotify OAuth integration (no password needed)
- ✅ Web-based interface
- ✅ Job queue and history
- ✅ Access from anywhere via browser

See **`webapp/README.md`** and **`WEBAPP_SETUP.md`** for setup instructions.

## Multi-User Support

These scripts support multiple users, each with their own Spotify and Instagram accounts. See **`MULTI_USER_SETUP.md`** for complete instructions.

**Quick summary:**
- Each user creates their own `.env` file with Spotify credentials
- Each user provides their own Instagram credentials when running the Apify actor
- Output files are timestamped to avoid conflicts
- The Apify actor can be shared - each user runs it with their own credentials

## Setup

### 1. Create a Spotify Developer App

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Log in with your Spotify account
3. Click "Create App"
4. Fill in the details:
   - **App Name**: Artist Follower (or whatever you like)
   - **App Description**: Follows artists from saved tracks
   - **Redirect URI**: `http://127.0.0.1:8888/callback`
5. Check the box to agree to terms
6. Click "Save"
7. Click "Settings" to view your **Client ID** and **Client Secret**

### 2. Configure Credentials

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```
SPOTIFY_CLIENT_ID=your_actual_client_id
SPOTIFY_CLIENT_SECRET=your_actual_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## Main Menu

The easiest way to use all tools is through the main menu:

```bash
python spotify_tools.py
```

This provides an interactive menu to select which utility you want to use.

## Usage

### Individual Scripts

You can also run scripts directly:

```bash
python follow_artists.py
python find_concerts.py
python randomize_playlists.py
```

On first run, a browser window will open asking you to authorize the app. After authorization, you'll be redirected to `127.0.0.1:8888/callback` - the script will capture this and continue.

The script will:
1. Fetch all your saved/liked tracks
2. Extract unique artists from those tracks
3. Check which artists you already follow
4. Offer to follow all the new artists

## Features

- **Saved Tracks**: Follows artists from your liked songs
- **Top Artists**: Optionally include your top artists from Spotify's algorithm
- **Deduplication**: Won't try to follow artists you already follow
- **Rate Limiting**: Built-in delays to respect Spotify's API limits
- **Preview**: Shows you who you'll follow before doing it
- **Confirmation**: Asks for confirmation before making changes

## Troubleshooting

### "INVALID_CLIENT: Invalid redirect URI"
Make sure the redirect URI in your Spotify app settings matches exactly: `http://127.0.0.1:8888/callback`

### Authentication Issues
Delete the `.spotify_cache` file to force re-authentication:
```bash
rm .spotify_cache
```

### Rate Limiting
If you hit rate limits, wait a few minutes and try again. The script has built-in delays but very large libraries might still hit limits.

---

## Concert Finder

Find upcoming concerts for your followed artists in your area.

### Usage

```bash
python find_concerts.py
```

The script will:
1. Fetch all artists you follow on Spotify
2. Query Bandsintown for upcoming events
3. Filter by your location and time preferences
4. Display concerts sorted by date

### Features

- **Location filtering**: Search by city, state, or country
- **Time range**: Specify how many months ahead to search
- **Save results**: Export concert list to a text file
- **Direct ticket links**: Get links to buy tickets

### Notes

- Concert data comes from [Bandsintown](https://www.bandsintown.com/)
- Some artists may not have data in Bandsintown
- The script respects API rate limits (may take a minute for large follow lists)

---

## Playlist Randomizer

Randomize the order of tracks in all your playlists.

### Usage

```bash
python randomize_playlists.py
```

The script will:
1. Fetch all playlists you own
2. Show you a list of playlists
3. Ask for confirmation (this modifies playlists!)
4. Optionally let you exclude specific playlists
5. Randomize the track order in each playlist

### Features

- **Selective randomization**: Choose which playlists to randomize
- **Safe operation**: Only modifies playlists you own
- **Large playlist support**: Handles playlists with 100+ tracks
- **Confirmation prompts**: Prevents accidental changes
- **Independent randomization**: Each playlist is randomized separately - tracks never leave their original playlist

### Notes

- **Tracks stay in their original playlists** - randomization only shuffles the order within each playlist, never mixing tracks across playlists
- Only randomizes playlists you **own** (not playlists you follow)
- This action **cannot be easily undone** - make sure you want to randomize!
- Changes may take a moment to appear in the Spotify app
- Collaborative playlists are included if you own them

---

## Instagram Account Finder

Find Instagram accounts for artists you follow on Spotify.

### Usage

```bash
python find_instagram_accounts.py
```

The script will:
1. Fetch all artists you follow on Spotify
2. Search for their Instagram accounts
3. Generate a list of Instagram URLs
4. Save results to files for easy access

### Features

- **Multiple search modes**: Quick, thorough, or manual
- **Export results**: Save to JSON and text files
- **Open in browser**: Optionally open found accounts in your browser
- **Smart guessing**: Generates potential Instagram URLs based on artist names

### Important Notes

⚠️ **Instagram API Limitations**: Instagram's official API does **not** allow automated following of users. This is a security/privacy restriction by Meta.

**What this script does:**
- ✅ Finds Instagram account URLs for your followed artists
- ✅ Generates a list you can use to manually follow artists
- ✅ Opens accounts in browser for easy access
- ⚠️ **Optional**: Browser automation using Selenium (RISKY - see warnings below)

**What this script cannot do:**
- ❌ Use official Instagram API to follow (not supported)
- ❌ Guarantee 100% accuracy (some accounts may not be found)

### Automated Following Options

#### ✅ RECOMMENDED: PhantomBuster or Apify

**Why use these services:**
- ✅ Better anti-bot detection handling
- ✅ Managed rate limiting and safety measures
- ✅ Cookie/session management
- ✅ Lower risk of account restrictions
- ✅ More reliable than raw automation

**How to use:**
1. Run the script to generate Instagram account data
2. The script exports:
   - **CSV file**: Import into PhantomBuster/Apify
   - **URLs file**: One Instagram URL per line (easy import)
   - **JSON file**: Full data for custom integrations
3. Import the CSV or URLs file into your chosen service
4. Configure the automation with safe rate limits (<40/hour)

**Services:**
- **PhantomBuster**: https://phantombuster.com - Has Instagram Follow automation
- **Apify**: https://apify.com - Instagram automation actors available

**Setup Guides:**
- See `APIFY_SETUP.md` for detailed Apify setup instructions

#### ⚠️ Alternative: Raw Selenium (NOT RECOMMENDED)

The script includes an **optional** browser automation feature using Selenium, but this is **NOT RECOMMENDED** due to higher risk.

⚠️ **STRONG WARNINGS:**
- Instagram actively fights automation and may detect this
- **Risks include:**
  - Action blocks (24-72 hour cooldowns on follow actions)
  - Temporary restrictions (slower follow limits)
  - **Permanent account suspension** (if detected as spammy/botted behavior)

**If you must use Selenium:**
- Keep follows to **<40 per hour**
- Add random delays between actions (script includes this)
- Don't run 24/7 - space it out over multiple days
- Monitor your account for restrictions
- Use at your own risk

**Requirements:**
```bash
pip install selenium
brew install chromedriver  # macOS
```

**We strongly recommend using PhantomBuster or Apify instead.**

### How to Use

1. Run the script to find Instagram accounts
2. Review the generated list
3. Manually visit each Instagram URL
4. Follow the artists you want on Instagram

The script saves results to files so you can work through the list at your own pace.

