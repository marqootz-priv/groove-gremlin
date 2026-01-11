# Automatic Deployment Setup ✅

## What's Been Configured

GitHub Actions workflows have been set up for automatic deployment:

1. **`.github/workflows/deploy-heroku.yml`** - Auto-deploys web app to Heroku
2. **`.github/workflows/deploy-apify.yml`** - Auto-deploys Apify actor  
3. **`.github/workflows/deploy-both.yml`** - Smart deployment (only deploys what changed)

## Required Setup (One-Time)

### Add GitHub Secrets

Go to: **https://github.com/marqootz-priv/groove-gremlin/settings/secrets/actions**

Click **"New repository secret"** and add:

#### 1. `HEROKU_API_KEY`
- **Get it from:** https://dashboard.heroku.com/account
- Click **"Reveal"** next to "API Key"
- Copy the entire key

#### 2. `HEROKU_EMAIL`
- Your Heroku account email address
- The email you use to log into Heroku

#### 3. `APIFY_API_TOKEN`
- **Get it from:** https://console.apify.com/account/integrations
- Click **"Create"** under "Personal API tokens"
- Copy the token (starts with `apify_api_...`)

## How It Works

### Automatic Deployment

When you push to `glydways-vr-visualizer` or `main` branch:

- **Changes to `webapp/`** → Automatically deploys to Heroku
- **Changes to `apify_actor/`** → Automatically deploys to Apify
- **Both change** → Both deploy automatically

### Manual Deployment

1. Go to: **GitHub Repo → Actions**
2. Select a workflow (Deploy to Heroku, Deploy to Apify, or Deploy to Both)
3. Click **"Run workflow"**
4. Select branch and click **"Run workflow"**

## Project Structure

```
/Users/markmanfrey/LOCAL_DEV/spotify/
├── webapp/              # Heroku web app (deploys from here)
│   ├── app.py
│   ├── Procfile
│   ├── requirements.txt
│   └── templates/
└── apify_actor/         # Apify actor (deploys from here)
    ├── main.py
    ├── Dockerfile
    ├── requirements.txt
    └── actor.json
```

## Testing

1. **Add the secrets** (see above)
2. **Make a small change** (e.g., add a comment to a file)
3. **Commit and push:**
   ```bash
   git add .
   git commit -m "Test deployment"
   git push origin glydways-vr-visualizer
   ```
4. **Check GitHub Actions:**
   - Go to: https://github.com/marqootz-priv/groove-gremlin/actions
   - You should see the workflow running
   - Wait for it to complete (green checkmark = success)

## Current Configuration

- **Repository:** https://github.com/marqootz-priv/groove-gremlin
- **Heroku App:** `groove-gremlin` (https://groove-gremlin.herokuapp.com)
- **Apify Actor:** `fulfilling_relish/spotify-artists-instagram-follow`
- **GitHub Branch:** `glydways-vr-visualizer` (also works with `main`)

## Troubleshooting

### Workflow doesn't run
- ✅ Check secrets are added correctly
- ✅ Verify you're pushing to `glydways-vr-visualizer` or `main`
- ✅ Check file paths match workflow filters

### Heroku deployment fails
- Check `HEROKU_API_KEY` is valid
- Verify app name: `groove-gremlin`
- Check Heroku logs: `heroku logs --tail --app groove-gremlin`

### Apify deployment fails
- Check `APIFY_API_TOKEN` is valid
- Verify actor exists: https://console.apify.com/actors
- Test manually: `cd apify_actor && apify push`

## Next Steps

1. **Add the 3 secrets** to GitHub (see above)
2. **Test with a small change**
3. **Enjoy automatic deployments!** 🚀

Once secrets are added, every push will automatically deploy your changes!
