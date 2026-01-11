# How to Rename Apify Actors

If you have actors in Apify with generic names (like "my-actor" or "undefined"), here's how to rename them:

## Method 1: Rename in Apify Console (Easiest)

1. Go to [Apify Console](https://console.apify.com/actors)
2. Find the actor you want to rename
3. Click on the actor to open it
4. Click the **Settings** tab (or gear icon)
5. Find the **Name** field
6. Change it to something descriptive like:
   - `spotify-artists-instagram-follow`
   - `instagram-follow-spotify-artists`
   - `follow-artists-instagram`
7. Click **Save**

## Method 2: Use Apify CLI

If you know the actor ID, you can rename it via CLI:

```bash
# List your actors
apify actors list

# Update actor name (replace ACTOR_ID with your actor ID)
apify actors update ACTOR_ID --name "spotify-artists-instagram-follow"
```

## Method 3: Delete and Recreate

If the actors are test/empty actors:

1. Delete the generic actors in Apify Console
2. Make sure your local `actor.json` has the correct name:
   ```json
   {
     "name": "spotify-artists-instagram-follow",
     ...
   }
   ```
3. Push again: `apify push`

## Current Actor Configuration

Your local actor is configured with:
- **Name**: `spotify-artists-instagram-follow`
- **Title**: "Follow Spotify Artists on Instagram"

When you push this, it will create/update an actor with this name.

## Finding Your Actors

To see all your actors:
```bash
apify actors list
```

Or visit: https://console.apify.com/actors

## Recommended Names

For your use case, good actor names would be:
- `spotify-artists-instagram-follow` ✅ (current)
- `instagram-follow-spotify-artists`
- `follow-spotify-artists-instagram`
- `spotify-to-instagram-follow`

Choose something that:
- Is descriptive
- Uses lowercase and hyphens
- Is unique to you (add your username if needed)
