#!/bin/bash
# Script to verify GitHub Secrets are set correctly for deployment

echo "🔍 Verifying GitHub Secrets for Deployment..."
echo ""

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) is not installed."
    echo "   Install it with: brew install gh"
    exit 1
fi

# Check if authenticated
if ! gh auth status &>/dev/null; then
    echo "⚠️  Not authenticated with GitHub. Logging in..."
    gh auth login
fi

# Get repository name
REPO="marqootz-priv/groove-gremlin"

echo "📋 Checking secrets for repository: $REPO"
echo ""

# List all secrets
echo "🔐 Current secrets in repository:"
gh secret list --repo "$REPO"
echo ""

# Check for required secrets
REQUIRED_SECRETS=("HEROKU_API_KEY" "HEROKU_EMAIL" "APIFY_API_TOKEN")
MISSING_SECRETS=()

echo "✅ Checking required secrets..."
for secret in "${REQUIRED_SECRETS[@]}"; do
    if gh secret list --repo "$REPO" | grep -q "^$secret"; then
        echo "   ✓ $secret is set"
    else
        echo "   ❌ $secret is MISSING"
        MISSING_SECRETS+=("$secret")
    fi
done

echo ""

if [ ${#MISSING_SECRETS[@]} -eq 0 ]; then
    echo "✅ All required secrets are set!"
    echo ""
    echo "📝 To view secret values (you'll need to set them again):"
    echo "   - HEROKU_API_KEY: Get from https://dashboard.heroku.com/account"
    echo "   - HEROKU_EMAIL: Your Heroku account email"
    echo "   - APIFY_API_TOKEN: Get from https://console.apify.com/account/integrations"
    echo ""
    echo "💡 Note: GitHub doesn't allow viewing secret values for security reasons."
    echo "   If you need to update them, use: ./add_github_secrets.sh"
else
    echo "❌ Missing secrets: ${MISSING_SECRETS[*]}"
    echo ""
    echo "📝 To add missing secrets:"
    echo "   1. Run: ./add_github_secrets.sh"
    echo "   2. Or manually add them at:"
    echo "      https://github.com/$REPO/settings/secrets/actions"
    exit 1
fi
