# Deployment Debugging Guide

## Issue: Workflows Run But Heroku/Apify Don't Deploy

If you see the GitHub Actions workflow running but Heroku and Apify aren't getting new builds, follow these steps:

## Step 1: Check Workflow Run Status

1. Go to: https://github.com/marqootz-priv/groove-gremlin/actions
2. Click on the latest workflow run
3. Check which jobs ran:
   - ✅ **"Detect Changes"** should run
   - ✅ **"Deploy Web App to Heroku"** should run if `webapp/` changed
   - ✅ **"Deploy Actor to Apify"** should run if `apify_actor/` changed

## Step 2: Check If Jobs Are Being Skipped

Look for jobs marked as **"Skipped"** (gray icon). This means the condition wasn't met.

### Common Reasons Jobs Are Skipped:

1. **No relevant files changed**: The workflow only deploys when files in `webapp/` or `apify_actor/` are modified
2. **Condition not met**: Check the "Debug - Check job condition" step output

### How to Force Deployment:

Use **"Run workflow"** button (manual trigger):
1. Go to Actions tab
2. Select "Deploy to Heroku and Apify" workflow
3. Click "Run workflow"
4. Select branch: `main`
5. Click "Run workflow"

This bypasses the change detection and forces both deployments.

## Step 3: Check Debug Output

The workflow now includes debug steps. Look for:

### In "Detect Changes" job:
- `webapp changed: true/false`
- `apify changed: true/false`
- List of modified files

### In "Deploy Web App to Heroku" job:
- Condition check results
- Secret verification (should show ✅)
- Heroku deployment logs

### In "Deploy Actor to Apify" job:
- Condition check results
- Secret verification (should show ✅)
- Apify login status
- Actor structure verification
- Apify push logs

## Step 4: Verify Secrets Are Correct

Run the verification script:
```bash
./verify_deployment_secrets.sh
```

This checks if all required secrets are set. If any are missing:
```bash
./add_github_secrets.sh
```

## Step 5: Check Specific Error Messages

### Heroku Deployment Issues:

**Error: "Invalid credentials"**
- Verify `HEROKU_API_KEY` is correct
- Get it from: https://dashboard.heroku.com/account
- Make sure you copied the entire key

**Error: "App not found"**
- Verify app name: `groove-gremlin`
- Check: https://dashboard.heroku.com/apps/groove-gremlin

**Error: "Permission denied"**
- Verify `HEROKU_EMAIL` matches your Heroku account email
- Check you have access to the app

### Apify Deployment Issues:

**Error: "Invalid API token"**
- Verify `APIFY_API_TOKEN` starts with `apify_api_`
- Get it from: https://console.apify.com/account/integrations
- Make sure you created a **Personal API token** (not organization token)

**Error: "Actor not found" or "Permission denied"**
- Verify the actor exists: https://console.apify.com/actors
- Check actor name matches: `spotify-artists-instagram-follow`
- Verify username: `fulfilling_relish`

**Error: "actor.json not found"**
- This shouldn't happen, but check the workflow logs
- Verify `apify_actor/actor.json` exists in the repository

## Step 6: Test Manual Deployment

### Test Heroku Deployment Locally:

```bash
cd webapp
heroku login
heroku git:remote -a groove-gremlin
git push heroku main
```

### Test Apify Deployment Locally:

```bash
cd apify_actor
apify login
apify push
```

If these work locally but not in GitHub Actions, it's likely a secret/permission issue.

## Step 7: Check Workflow Permissions

GitHub Actions needs permission to access secrets. This should be automatic, but verify:

1. Go to: https://github.com/marqootz-priv/groove-gremlin/settings/actions
2. Under "Workflow permissions", ensure:
   - ✅ "Read and write permissions" is selected
   - ✅ "Allow GitHub Actions to create and approve pull requests" is checked (if needed)

## Step 8: Common Issues and Solutions

### Issue: "Job skipped" - No deployments run

**Cause**: No files in `webapp/` or `apify_actor/` were changed

**Solution**: 
- Make a change to a file in the relevant directory
- Or use "Run workflow" button to force deployment

### Issue: "Secret not found" error

**Cause**: Secret name mismatch or secret not set

**Solution**:
- Run `./verify_deployment_secrets.sh` to check
- Verify secret names match exactly (case-sensitive):
  - `HEROKU_API_KEY` (not `heroku_api_key`)
  - `HEROKU_EMAIL` (not `heroku_email`)
  - `APIFY_API_TOKEN` (not `apify_api_token`)

### Issue: Heroku deploy succeeds but no new build

**Cause**: Heroku might be using cached build or the action isn't actually deploying

**Solution**:
- Check Heroku dashboard: https://dashboard.heroku.com/apps/groove-gremlin/activity
- Look for recent deployments
- Check if the action is actually pushing code (look for "git push" in logs)

### Issue: Apify push succeeds but actor not updated

**Cause**: Apify might need explicit version bump or the push didn't complete

**Solution**:
- Check Apify console: https://console.apify.com/actors
- Look at actor versions
- Check if there are any errors in the push logs
- Try running `apify push` locally to see detailed output

## Step 9: Enable More Verbose Logging

If you need more details, you can temporarily add:

```yaml
- name: Debug - Show all environment
  run: |
    echo "Event: ${{ github.event_name }}"
    echo "SHA: ${{ github.sha }}"
    echo "Ref: ${{ github.ref }}"
    env | grep -i heroku || true
    env | grep -i apify || true
```

## Getting Help

If issues persist:

1. **Check GitHub Actions logs**: Full error messages are in the workflow run logs
2. **Check Heroku logs**: `heroku logs --tail --app groove-gremlin`
3. **Check Apify console**: https://console.apify.com/actors for actor status
4. **Verify secrets are current**: Tokens/keys might have expired or been rotated

## Quick Checklist

- [ ] All secrets are set (run `./verify_deployment_secrets.sh`)
- [ ] Workflow is running (check Actions tab)
- [ ] Jobs aren't being skipped (check job status)
- [ ] Debug output shows correct values
- [ ] Secrets verification passes (✅ in logs)
- [ ] Deployment steps complete without errors
- [ ] Heroku/Apify show new builds/deployments
