# How to Use Your Apify Actor

Step-by-step guide to using your Instagram follow actor.

## Prerequisites

1. ✅ Actor is deployed to Apify (you've run `apify push`)
2. ✅ You have Instagram account credentials
3. ✅ You have a list of Instagram URLs to follow

## Step 1: Generate Instagram URLs and Apify Input

Get the Instagram accounts for your Spotify artists:

```bash
python find_instagram_accounts.py
```

This will automatically create:
- `instagram_urls_[timestamp].txt` - One URL per line
- `instagram_urls_[timestamp]_apify_input.json` - **Ready-to-use Apify input** ✅
- Plus CSV and other formats

## Step 2: Edit the Apify Input File

Open `instagram_urls_[timestamp]_apify_input.json` and add your Instagram credentials:

```json
{
  "urls": [
    "https://www.instagram.com/artist1/",
    "https://www.instagram.com/artist2/"
  ],
  "instagram_username": "your_instagram_username",
  "instagram_password": "your_instagram_password",
  "delay_min": 2,
  "delay_max": 4,
  "max_follows": 40,
  "headless": false
}
```

**Important**: Add your `instagram_username` and `instagram_password` to the JSON.

## Step 3: Run the Actor

You have two options:

### Option A: Run from Apify Console (Recommended)

1. Go to [Apify Console](https://console.apify.com/actors)
2. Find your actor: **"Follow Spotify Artists on Instagram"**
3. Click on it to open
4. Click **Start** or **Run** button
5. In the input section:
   - Either paste the JSON content from your file
   - Or upload the JSON file
6. Click **Start** to run the actor
7. Monitor the run in real-time

### Option B: Run from Command Line

```bash
# From the apify_actor directory
cd apify_actor

# Run with input file
apify run --input-file ../instagram_urls_[timestamp]_apify_input.json

# Or run with inline JSON
apify run --input '{"urls":["https://www.instagram.com/artist1/"],"instagram_username":"your_username","instagram_password":"your_password"}'
```

## Step 4: Monitor the Run

While the actor is running:

1. **Watch the Logs**: See real-time progress in Apify Console
2. **Check Status**: See how many accounts are being followed
3. **View Results**: Check the dataset for results

The actor will:
- Log in to Instagram
- Visit each URL
- Click "Follow" button
- Wait 2-4 seconds between follows
- Pause every 10 follows for safety

## Step 5: Check Results

After the run completes:

1. Go to the **Dataset** tab in Apify Console
2. View results - each row shows:
   - `url`: The Instagram profile URL
   - `status`: "followed", "failed", or "already following"
   - `timestamp`: When it was processed

## Input Parameters Explained

| Parameter | Description | Default | Recommended |
|-----------|-------------|---------|-------------|
| `urls` | Array of Instagram profile URLs | Required | Your artist URLs |
| `instagram_username` | Your Instagram username | Required | Your username |
| `instagram_password` | Your Instagram password | Required | Your password |
| `delay_min` | Min seconds between follows | 2 | 2-3 (safe) |
| `delay_max` | Max seconds between follows | 4 | 4-5 (safe) |
| `max_follows` | Max follows per run | 40 | 20-40 (safe) |
| `headless` | Run browser hidden | false | true for production |

## Safety Tips

⚠️ **Important Safety Guidelines:**

1. **Start Small**: Test with 5-10 URLs first
2. **Respect Limits**: Keep `max_follows` under 40 per run
3. **Space Out Runs**: Don't run multiple times per day
4. **Monitor Your Account**: Check Instagram for any restrictions
5. **Use Headless**: Set `headless: true` for production runs

## Troubleshooting

### "Login failed"
- Check your username/password are correct
- Instagram may require 2FA - you might need to use session cookies instead
- Try logging in manually first to verify credentials

### "Follow button not found"
- Profile may be private or restricted
- Profile may not exist
- Instagram UI may have changed

### "Rate limit exceeded"
- Reduce `max_follows` (try 20 instead of 40)
- Increase `delay_min` and `delay_max` (try 3-6 seconds)
- Wait longer between runs (hours/days)

### Actor won't start
- Check your input JSON is valid
- Make sure all required fields are present
- Verify you have enough compute units in your Apify plan

## Example: Complete Workflow

```bash
# 1. Get Instagram accounts from Spotify (creates Apify input automatically)
python find_instagram_accounts.py
# Choose search mode, wait for results
# This creates: instagram_urls_[timestamp]_apify_input.json

# 2. Edit the JSON file to add credentials
# Open instagram_urls_[timestamp]_apify_input.json
# Add: "instagram_username" and "instagram_password"

# 3. Run the actor
cd apify_actor
apify run --input-file ../instagram_urls_[timestamp]_apify_input.json

# 4. Monitor in Apify Console
# Visit: https://console.apify.com/actors
# Click on your actor to see the run
```

## Quick Reference

**Find your actor:**
- Console: https://console.apify.com/actors
- CLI: `apify actors list`

**Run actor:**
- Console: Click actor → Start → Paste input → Run
- CLI: `apify run --input-file input.json`

**View results:**
- Console: Actor → Dataset tab
- CLI: Results saved to Apify dataset

## Need Help?

- Check actor logs in Apify Console
- Review `apify_actor/README.md` for technical details
- Apify Docs: https://docs.apify.com
