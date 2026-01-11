# Setting Up Apify for Instagram Following

This guide walks you through using Apify to automatically follow Instagram accounts from your Spotify followed artists.

## Step 1: Sign Up for Apify

1. Go to [https://apify.com](https://apify.com)
2. Click **Sign up** (top right)
3. Create an account (you can use Google/GitHub to sign up quickly)
4. Choose a plan:
   - **Free tier**: Limited compute units, good for testing
   - **Starter plan**: $49/month - Better for regular use
   - You can start with free to test

## Step 2: Choose Your Approach

You have two options:

### Option A: Use Existing Actor (Easiest)

1. In Apify, go to the **Store** (top navigation)
2. Search for: `instagram follow` or `instagram automation`
3. Popular options:
   - **Instagram Auto Follow/UnFollow** actor
   - **Instagram Followers Scraper** (may have follow functionality)
   - Look for actors with "follow" in the name/description

**Note**: Apify's available actors change over time. If you can't find a follow actor, see Option B.

### Option B: Create Your Own Actor (More Control)

We've included a custom Apify actor template in `apify_actor/` directory.

**Why write your own?**
- ✅ More control over rate limiting and behavior
- ✅ Customized for your specific needs
- ✅ Runs on Apify's managed infrastructure (safer than raw Selenium)
- ✅ Reusable and shareable

**Setup:**
1. See `apify_actor/README.md` for detailed instructions
2. Install Apify CLI: `npm install -g apify-cli` or `pip install apify-cli`
3. Login: `apify login`
4. Deploy: `cd apify_actor && apify push`
5. Run from Apify Console

**Comparison:**
- **Apify Actor**: Managed infrastructure, better anti-detection, reusable, pay per use
- **Raw Selenium**: Full control, easier debugging, but higher risk of detection/bans

## Step 3: Prepare Your Data

1. Run the Instagram account finder script:
   ```bash
   python find_instagram_accounts.py
   ```

2. The script will automatically generate several files:
   - `instagram_urls_[timestamp]_apify_input.json` - **Ready-to-use Apify input** ✅
   - `instagram_urls_[timestamp].txt` - One URL per line
   - `instagram_accounts_[timestamp].csv` - CSV format
   - `instagram_accounts_[timestamp].json` - Full data

3. The Apify input file is already formatted - just add your credentials:
   ```json
   {
     "urls": [
       "https://www.instagram.com/artist1/",
       "https://www.instagram.com/artist2/"
     ],
     "delay_min": 2,
     "delay_max": 4,
     "max_follows": 40,
     "headless": false
     // Add: "instagram_username" and "instagram_password"
   }
   ```

## Step 4: How to Use the Actor

See **`HOW_TO_USE_ACTOR.md`** for complete step-by-step instructions on:
- Preparing your input data
- Running the actor
- Monitoring results
- Troubleshooting

Quick start:
1. Generate URLs: `python find_instagram_accounts.py`
2. Convert format: `python convert_to_apify_input.py instagram_urls_[timestamp].txt`
3. Add credentials to the JSON file
4. Run in Apify Console or via CLI

## Step 5: Configure the Apify Actor (If Using Existing Actor)

1. **Open the Instagram Follow actor** you found in Step 2
2. Click **Try for free** or **Run** button
3. You'll see an input configuration panel

### Input Configuration:

**For CSV import:**
- Look for an input field like:
  - `Instagram URLs` or `Profile URLs`
  - `Input data` or `CSV file`
  - `List of profiles to follow`

**Two ways to provide data:**

#### Option A: Upload CSV File
- If the actor supports file upload:
  - Click "Upload" or "Choose file"
  - Select your `instagram_accounts_[timestamp].csv`
  - The actor should extract the URLs from the CSV

#### Option B: Paste URLs (from URLs file)
- Open `instagram_urls_[timestamp].txt`
- Copy all URLs (one per line)
- Paste into the actor's input field (may need to be comma-separated or JSON format)

#### Option C: Use JSON format
- Some actors accept JSON input
- Use the JSON file if available

### Other Settings to Configure:

1. **Rate Limiting**:
   - Set delay between follows: **2-4 seconds minimum**
   - Max follows per hour: **<40** (to avoid restrictions)

2. **Authentication**:
   - You'll need to provide your Instagram credentials
   - Or use Instagram session cookies (more secure)
   - Follow Apify's instructions for authentication

3. **Safety Settings**:
   - Enable "Stop on error" (to pause if something goes wrong)
   - Set maximum follows per run (start with 20-30 to test)

## Step 5: Run the Actor

1. Click **Run** or **Start** button
2. Monitor the run in the Apify dashboard
3. Check logs for any errors
4. The actor will follow accounts according to your settings

## Step 6: Monitor and Adjust

- **Check your Instagram account** for any restrictions
- **Review Apify logs** to see which accounts were followed
- **Adjust rate limits** if you see warnings
- **Space out runs** - don't run 24/7, spread over days

## Alternative: Using PhantomBuster

If Apify doesn't have a suitable Instagram Follow actor, consider **PhantomBuster**:

1. Go to [https://phantombuster.com](https://phantombuster.com)
2. Sign up (free trial available)
3. Search for "Instagram Follow" automation
4. Import your CSV file
5. Configure rate limits and run

PhantomBuster often has more Instagram-specific automations.

## Troubleshooting

### "No Instagram Follow actor found"
- Apify's actor library changes - search for alternatives
- Consider using PhantomBuster instead
- Check Apify's community forum for recommendations

### "Authentication failed"
- Make sure you're providing valid Instagram credentials
- Some actors require session cookies instead of username/password
- Check the actor's documentation for auth requirements

### "Rate limit exceeded"
- Reduce the number of follows per run
- Increase delay between follows
- Wait longer between runs (hours/days)

### "CSV format not accepted"
- Try the URLs text file instead (one URL per line)
- Convert CSV to JSON if actor requires it
- Check actor documentation for exact format needed

## Best Practices

1. **Start small**: Test with 5-10 accounts first
2. **Monitor closely**: Watch for Instagram restrictions
3. **Respect limits**: Keep under 40 follows/hour
4. **Space it out**: Don't follow hundreds in one day
5. **Verify accounts**: Make sure the found Instagram accounts are correct before automating

## Cost Considerations

- **Apify Free**: Limited compute units, may not be enough for large lists
- **Apify Starter**: $49/month - Better for regular use
- **PhantomBuster**: ~$70/month for Instagram automations
- Consider the cost vs. manually following if you have a small list

## Need Help?

- Apify Documentation: https://docs.apify.com
- Apify Community: https://forum.apify.com
- Check actor-specific documentation in Apify Store
