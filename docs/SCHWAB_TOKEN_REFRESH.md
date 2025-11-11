# Schwab API Token Refresh Guide

## Overview

The Schwab API uses OAuth 2.0 for authentication. Tokens expire and need to be refreshed periodically.

## Token Types

1. **Access Token**: Short-lived (30 minutes), used for API requests
2. **Refresh Token**: Long-lived (7 days), used to obtain new access tokens

## When to Refresh

- **Access Token**: Automatically refreshed by the SchwabClient when expired
- **Refresh Token**: Manually refresh every 7 days to maintain continuous access

## How to Refresh Schwab Tokens

### Option 1: Using the Schwab Developer Portal (Recommended)

1. **Login to Schwab Developer Portal**
   - Go to: https://developer.schwab.com/
   - Login with your Schwab credentials

2. **Navigate to Your App**
   - Go to "My Apps"
   - Select your Volaris trading app

3. **Get New Tokens**
   - Click "Request OAuth Tokens"
   - Follow the OAuth flow to authorize your app
   - Copy the new `access_token` and `refresh_token`

4. **Update Environment Variables**
   ```bash
   # Update .env file or Render environment variables
   SCHWAB_ACCESS_TOKEN=your_new_access_token_here
   SCHWAB_REFRESH_TOKEN=your_new_refresh_token_here
   ```

5. **Restart Application** (if needed)
   - Render: Deployment will restart automatically when env vars change
   - Local: Restart your uvicorn server

### Option 2: Using the OAuth Flow Script (Advanced)

If you have the OAuth flow script set up:

```bash
# Run the OAuth flow script
python scripts/schwab_oauth_flow.py

# Follow the prompts to get new tokens
# Copy the tokens to your .env file or Render dashboard
```

### Option 3: Programmatic Refresh (Automated)

The `SchwabClient` automatically refreshes access tokens using the refresh token:

```python
from app.services.schwab import SchwabClient

# Client automatically refreshes when access token expires
client = SchwabClient()
quotes = await client.get_quotes(["AAPL", "MSFT"])
```

**Important**: This only works if the refresh token is still valid (< 7 days old).

## Setting Up Automatic Token Refresh

### GitHub Actions Reminder (Future Enhancement)

Create a GitHub Actions workflow to remind you to refresh tokens:

```yaml
# .github/workflows/token-reminder.yml
name: Schwab Token Refresh Reminder

on:
  schedule:
    - cron: "0 12 * * 1"  # Every Monday at noon

jobs:
  remind:
    runs-on: ubuntu-latest
    steps:
      - name: Check Token Age
        run: |
          echo "⚠️  Reminder: Schwab tokens expire every 7 days"
          echo "Please refresh tokens if needed: https://developer.schwab.com/"
```

## Troubleshooting

### Error: "Invalid refresh token"

**Cause**: Refresh token expired (> 7 days old)

**Solution**:
1. Go to Schwab Developer Portal
2. Request new OAuth tokens
3. Update `SCHWAB_REFRESH_TOKEN` in environment variables

### Error: "Access denied"

**Cause**: Schwab app permissions changed or revoked

**Solution**:
1. Check app status in Schwab Developer Portal
2. Ensure app has required permissions:
   - Market Data
   - Account Information (if using trading features)
3. Re-authorize if needed

### Error: "Rate limit exceeded"

**Cause**: Too many API requests

**Solution**:
1. Schwab has rate limits (120 requests/minute)
2. Check `SchwabClient` retry logic in `app/services/schwab.py`
3. Reduce refresh frequency in GitHub Actions workflows

## Token Security

### Best Practices

1. **Never commit tokens to git**
   - Tokens are in `.env` (gitignored)
   - Use Render environment variables for production

2. **Rotate tokens regularly**
   - Set calendar reminder for every 6 days
   - Refresh before 7-day expiration

3. **Monitor token usage**
   - Check Render logs for auth errors
   - Set up alerts for authentication failures

4. **Use environment-specific tokens**
   - Development: Personal Schwab account tokens
   - Production: Dedicated production account tokens

## Environment Variables

Required Schwab environment variables:

```bash
# .env or Render Environment Variables
SCHWAB_APP_KEY=your_app_key
SCHWAB_APP_SECRET=your_app_secret
SCHWAB_ACCESS_TOKEN=your_access_token
SCHWAB_REFRESH_TOKEN=your_refresh_token
SCHWAB_CALLBACK_URL=https://127.0.0.1:8000/callback  # or your production callback
```

## Provider Fallback

If Schwab tokens expire and volume data is needed:

1. **Tiingo**: Free tier, daily EOD data with volume
2. **Alpaca**: Free market data API, daily bars
3. **Polygon**: Free tier with delayed data

Configure fallback in `app/services/provider_manager.py`:

```python
# Priority order for EOD data (includes volume)
DataType.EOD: [tiingo_client, alpaca_client, schwab_client]
```

## Links

- **Schwab Developer Portal**: https://developer.schwab.com/
- **Schwab API Docs**: https://developer.schwab.com/products/trader-api--individual
- **OAuth 2.0 Spec**: https://oauth.net/2/
