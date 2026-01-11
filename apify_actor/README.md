# Apify Actor: Instagram Follow from List

This is a custom Apify Actor that follows Instagram accounts from a list of URLs.

## Multi-User Support

✅ **This actor supports multiple users!** Each user can run it with their own:
- Instagram credentials (username/password)
- List of URLs to follow
- Rate limiting preferences

Results are stored separately per user in their own Apify account. The actor can be:
- **Shared publicly** - anyone can use it with their own credentials
- **Used by a team** - each member uses their own Instagram account
- **Run multiple times** - each run is independent

See `../MULTI_USER_SETUP.md` for complete multi-user setup instructions.

## Why Write Your Own Actor vs. Raw Selenium?

### ✅ Advantages of Apify Actor:

1. **Managed Infrastructure**: Runs on Apify's servers, no need to manage your own
2. **Built-in Scaling**: Apify handles resource allocation
3. **Better Anti-Detection**: Apify's infrastructure may be less likely to be flagged
4. **Reusable**: Can be run multiple times, shared with others
5. **Monitoring**: Built-in logging and monitoring
6. **Input/Output Handling**: Easy data input/output management
7. **Cost Effective**: Pay per use, not for idle infrastructure

### ❌ Disadvantages:

1. **Learning Curve**: Need to learn Apify SDK
2. **Less Control**: Can't debug as easily as local Selenium
3. **Cost**: Pay per run (though free tier available)

### Raw Selenium Comparison:

- **Pros**: Full control, easy debugging, free to run locally
- **Cons**: Higher detection risk, need to manage infrastructure, account more likely to be banned

## Setup Instructions

### 1. Install Apify CLI

```bash
npm install -g apify-cli
```

Or with pip:
```bash
pip install apify-cli
```

### 2. Login to Apify

```bash
apify login
```

### 3. Create Actor from This Template

```bash
cd apify_actor
apify create
```

Or push existing code:
```bash
apify push
```

### 4. Configure Input

In Apify Console:
1. Go to your actor
2. Set input:
   ```json
   {
     "urls": [
       "https://www.instagram.com/artist1/",
       "https://www.instagram.com/artist2/"
     ],
     "instagram_username": "your_username",
     "instagram_password": "your_password",
     "delay_min": 2,
     "delay_max": 4,
     "max_follows": 40,
     "headless": false
   }
   ```

### 5. Run the Actor

```bash
apify run
```

Or run from Apify Console.

## Using with Spotify Data

1. Run the Instagram account finder:
   ```bash
   python find_instagram_accounts.py
   ```

2. Get the URLs file: `instagram_urls_[timestamp].txt`

3. Convert to Apify input format:
   ```bash
   python convert_to_apify_input.py instagram_urls_[timestamp].txt
   ```
   
   This creates a JSON file with the proper format. Then:
   - Add your `instagram_username` and `instagram_password` to the JSON
   - Or paste the JSON into Apify Console and add credentials there

4. Use the JSON file as input in Apify actor

## Input Schema

- `urls` (required): Array of Instagram profile URLs
- `instagram_username` (required): Your Instagram username
- `instagram_password` (required): Your Instagram password
- `delay_min` (optional): Minimum delay between follows (default: 2)
- `delay_max` (optional): Maximum delay between follows (default: 4)
- `max_follows` (optional): Max follows per run (default: 40)
- `headless` (optional): Run browser headless (default: false)

## Output

The actor outputs:
- Dataset with results for each URL (followed/failed/already following)
- Summary in actor output with counts

## Safety Features

- Rate limiting (configurable delays)
- Max follows per run limit
- Pauses every 10 follows
- Handles "already following" cases
- Error handling and logging

## Best Practices

1. **Start Small**: Test with 5-10 URLs first
2. **Respect Limits**: Keep under 40 follows/hour
3. **Space Out Runs**: Don't run multiple times per day
4. **Monitor**: Check your Instagram account for restrictions
5. **Use Headless**: Set `headless: true` for production runs

## Troubleshooting

### "Login failed"
- Check credentials are correct
- Instagram may require 2FA - you may need to use session cookies instead

### "Follow button not found"
- Profile may be private or restricted
- Profile may not exist
- Instagram UI may have changed

### "Rate limit exceeded"
- Reduce `max_follows`
- Increase `delay_min` and `delay_max`
- Wait longer between runs

## Cost

- **Free Tier**: Limited compute units (good for testing)
- **Starter**: $49/month for regular use
- **Pay per use**: Based on compute units consumed

## Alternative: Use Existing Actors

Before deploying this, check if Apify already has an Instagram Follow actor:
- Search Apify Store for "instagram follow"
- May be more polished and tested
- This custom actor is for when you need specific control
