# Multi-User Setup Guide

This guide explains how multiple users can use these scripts and the Apify actor with their own Spotify and Instagram accounts.

## Overview

The scripts and actor are designed to support multiple users:
- ✅ Each user has their own Spotify credentials (via `.env` file)
- ✅ Each user provides their own Instagram credentials (via Apify input)
- ✅ Output files are organized by user/timestamp
- ✅ The Apify actor can be shared and used by multiple people

## Setup for Individual Users

### Step 1: Each User Creates Their Own `.env` File

Each user needs their own Spotify API credentials:

```bash
# User 1 creates: .env
SPOTIFY_CLIENT_ID=user1_client_id
SPOTIFY_CLIENT_SECRET=user1_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback

# User 2 creates: .env.user2 (or uses their own directory)
SPOTIFY_CLIENT_ID=user2_client_id
SPOTIFY_CLIENT_SECRET=user2_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

**Note**: Each user needs to:
1. Create their own Spotify Developer App at https://developer.spotify.com/dashboard
2. Get their own Client ID and Client Secret
3. Set up their own `.env` file

### Step 2: Each User Runs the Scripts

Each user runs the scripts with their own credentials:

```bash
# User 1
python find_instagram_accounts.py
# Uses .env file → generates files with their Spotify data

# User 2 (in their own directory or with different .env)
python find_instagram_accounts.py
# Uses their .env → generates files with their Spotify data
```

**Output files are timestamped**, so multiple users won't overwrite each other's files.

### Step 3: Each User Uses Their Own Instagram Credentials

When running the Apify actor, each user provides their own Instagram credentials in the input:

```json
{
  "urls": [...],
  "instagram_username": "user1_instagram",  // User 1's account
  "instagram_password": "user1_password",
  ...
}
```

## Sharing the Apify Actor

### Option A: Public Actor (Anyone Can Use)

1. **Make the actor public** in Apify Console:
   - Go to Actor Settings
   - Set visibility to "Public" or "Unlisted"
   - Share the actor URL

2. **Each user runs it with their own input**:
   - They provide their own Instagram credentials
   - They use their own list of URLs
   - Results are stored in their own Apify account

### Option B: Private Actor (Team/Organization)

1. **Keep actor private** but share with team:
   - Add team members in Apify Console
   - They can run the actor with their own credentials

2. **Each team member**:
   - Uses their own Instagram account
   - Provides their own URLs
   - Gets their own results

## Organizing Output Files

### Option 1: Separate Directories (Recommended)

Each user works in their own directory:

```
spotify/
├── user1/
│   ├── .env
│   ├── instagram_urls_123_apify_input.json
│   └── ...
├── user2/
│   ├── .env
│   ├── instagram_urls_456_apify_input.json
│   └── ...
└── shared/
    ├── apify_actor/
    └── scripts/
```

### Option 2: User Prefix in Filenames

Modify scripts to include username in filenames (see customization below).

### Option 3: Timestamped Files (Current)

Current approach - files are timestamped, so users won't conflict:
- `instagram_urls_1767793973_apify_input.json` (User 1, timestamp 1)
- `instagram_urls_1767795124_apify_input.json` (User 2, timestamp 2)

## Customization for Multi-User

### Add Username to Filenames

You can modify `find_instagram_accounts.py` to include username:

```python
# In find_instagram_accounts.py, add:
import getpass

# Get current username
current_user = getpass.getuser()  # or os.getenv('USER')
timestamp = int(time.time())

# Use in filenames:
apify_input_filename = f"instagram_urls_{current_user}_{timestamp}_apify_input.json"
```

### Environment-Specific Config

Create user-specific config files:

```bash
# .env.user1
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...

# .env.user2
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
```

Then load specific env file:
```python
load_dotenv('.env.user1')  # or based on user selection
```

## Apify Actor: Multi-User Support

The actor already supports multiple users because:

1. **Credentials are per-run**: Each run uses different Instagram credentials
2. **Results are per-user**: Each user's results go to their own Apify dataset
3. **No shared state**: Each run is independent

### Running for Different Users

**User 1:**
```json
{
  "urls": ["https://www.instagram.com/artist1/"],
  "instagram_username": "user1_instagram",
  "instagram_password": "user1_password"
}
```

**User 2:**
```json
{
  "urls": ["https://www.instagram.com/artist2/"],
  "instagram_username": "user2_instagram",
  "instagram_password": "user2_password"
}
```

Both can use the same actor, just with different input!

## Best Practices

### For Individual Users

1. **Keep your `.env` file private** - don't commit it to git
2. **Use your own Spotify Developer App** - don't share credentials
3. **Use your own Instagram account** - don't share passwords
4. **Organize your files** - use your own directory or prefix

### For Teams/Organizations

1. **Share the actor**, not credentials
2. **Each member** uses their own accounts
3. **Use Apify teams** for shared actors
4. **Set up separate Spotify apps** per user/team

### For Public Sharing

1. **Make actor public** if you want others to use it
2. **Document requirements** clearly
3. **Each user** provides their own credentials
4. **No credential sharing** - everyone uses their own

## Security Considerations

⚠️ **Important Security Notes:**

1. **Never share credentials**:
   - Don't commit `.env` files to git
   - Don't share Instagram passwords
   - Don't share Spotify Client Secrets

2. **Use environment variables**:
   - Keep credentials in `.env` files
   - Add `.env` to `.gitignore`
   - Use different `.env` files per user

3. **Apify secrets**:
   - Use Apify's secret storage for passwords
   - Don't hardcode credentials in input
   - Use environment variables in Apify if possible

4. **Access control**:
   - Keep actors private unless needed public
   - Use Apify teams for collaboration
   - Review who has access

## Example: Team Setup

```bash
# Team member 1
cd ~/spotify-user1
cp .env.example .env
# Edit .env with their Spotify credentials
python find_instagram_accounts.py
# Edit generated JSON with their Instagram credentials
apify run --input-file instagram_urls_123_apify_input.json

# Team member 2
cd ~/spotify-user2
cp .env.example .env
# Edit .env with their Spotify credentials
python find_instagram_accounts.py
# Edit generated JSON with their Instagram credentials
apify run --input-file instagram_urls_456_apify_input.json
```

## Troubleshooting

### "Credentials already in use"
- Each user needs their own Spotify Developer App
- Don't share Client ID/Secret between users

### "File conflicts"
- Use separate directories per user
- Or add username prefix to filenames
- Timestamps already prevent most conflicts

### "Actor access denied"
- Make sure actor is public, or
- Add user to Apify team
- Check actor permissions

## Summary

✅ **Scripts**: Each user has their own `.env` file with Spotify credentials
✅ **Actor**: Each user provides their own Instagram credentials per run
✅ **Output**: Files are timestamped to avoid conflicts
✅ **Sharing**: Actor can be shared, credentials stay private

The system is designed to be multi-user friendly out of the box!
