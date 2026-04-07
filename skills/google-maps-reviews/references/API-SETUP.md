# Google My Business API Setup

## Prerequisites

1. Google Cloud Project with My Business API enabled
2. OAuth 2.0 credentials downloaded
3. Python packages: `google-auth`, `google-auth-oauthlib`, `google-api-python-client`

## Step 1: Enable API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable **Google My Business API**
4. Navigate to **APIs & Services > Credentials**

## Step 2: Create OAuth Credentials

1. Click **Create Credentials > OAuth 2.0 Client ID**
2. Application type: **Desktop app**
3. Name: `OpenClaw GMB Access`
4. Click **Create**
5. Download JSON credentials file
6. Save as `~/.openclaw/credentials/gmb_credentials.json`

## Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services > OAuth consent screen**
2. User Type: **Internal** (if workspace) or **External**
3. Add required info (app name, support email)
4. Add scope: `https://www.googleapis.com/auth/business.manage`
5. Add test users (your email) if External

## Step 4: Install Dependencies

```bash
pip3 install google-auth google-auth-oauthlib google-api-python-client
```

## Step 5: First Authentication

Run the script for the first time:

```bash
python3 scripts/gmb_reviews.py list-accounts
```

This will:
1. Open browser for OAuth consent
2. Save token to `~/.openclaw/credentials/gmb_token.json`
3. List your Google My Business accounts

## Step 6: Get Account and Location IDs

```bash
# List accounts
python3 scripts/gmb_reviews.py list-accounts

# List locations (replace with your account ID)
python3 scripts/gmb_reviews.py list-locations --account accounts/YOUR_ACCOUNT_ID
```

Save these IDs for use in the skill.

## Troubleshooting

### "API has not been used in project"
- Enable Google My Business API in Cloud Console
- Wait 5-10 minutes for propagation

### "Access Not Configured"
- Verify OAuth consent screen is configured
- Check that scope `https://www.googleapis.com/auth/business.manage` is added
- Add your email as test user if using External app type

### "Invalid Grant"
- Delete `~/.openclaw/credentials/gmb_token.json`
- Re-authenticate with `python3 scripts/gmb_reviews.py list-accounts`

### Permission Denied
- Verify you have owner/manager access to the Google My Business account
- Check that the correct Google account is authenticated

## API Documentation

- [Google My Business API Reference](https://developers.google.com/my-business/reference/rest)
- [Review Management](https://developers.google.com/my-business/content/review-data)
- [OAuth 2.0 Setup](https://developers.google.com/identity/protocols/oauth2)
