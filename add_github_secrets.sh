#!/bin/bash
# Script to add GitHub Secrets for automatic deployment
# NOTE: Replace the placeholder values with your actual credentials

echo "🔐 Adding GitHub Secrets..."

# Authenticate if needed
if ! gh auth status &>/dev/null; then
    echo "⚠️  Need to authenticate with GitHub first..."
    gh auth login
fi

# Add secrets (replace with your actual values)
echo "📧 Adding HEROKU_EMAIL..."
read -p "Enter your Heroku email: " heroku_email
gh secret set HEROKU_EMAIL --repo marqootz-priv/groove-gremlin --body "$heroku_email"

echo "🔑 Adding APIFY_API_TOKEN..."
read -sp "Enter your Apify API token: " apify_token
echo
gh secret set APIFY_API_TOKEN --repo marqootz-priv/groove-gremlin --body "$apify_token"

echo "🔑 Adding HEROKU_API_KEY..."
read -sp "Enter your Heroku API key: " heroku_key
echo
gh secret set HEROKU_API_KEY --repo marqootz-priv/groove-gremlin --body "$heroku_key"

echo ""
echo "✅ Verifying secrets..."
gh secret list --repo marqootz-priv/groove-gremlin

echo ""
echo "🎉 Done! Secrets added. Automatic deployments should now work!"
