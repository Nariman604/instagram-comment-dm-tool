# Instagram Comment-to-DM Automation Tool

A production-ready full-stack web application that automatically replies to Instagram post comments and sends DMs to commenters based on keyword-triggered campaigns.

## Project Overview

When someone comments on your Instagram post, the tool:
1. Checks if the comment matches keywords in an active campaign
2. Automatically **replies to the comment** publicly
3. Automatically **sends a DM** to the commenter privately

## Step-by-Step Instagram API Setup

### 1. Create a Facebook Developer App
1. Go to https://developers.facebook.com/apps and click **Create App**
2. Select **Business** as the app type
3. Under **Products**, add **Instagram Graph API** and **Messenger**

### 2. Required Permissions
- `instagram_basic` - Read media and profile info
- `instagram_manage_comments` - Reply to comments
- `instagram_manage_messages` - Send DMs (**requires Meta app review**)
- `pages_show_list` - List Facebook Pages
- `pages_read_engagement` - Read engagement data

> **Note:** `instagram_manage_messages` requires Meta app review. Until approved, you can only DM users who have previously messaged your business first.

### 3. Convert Instagram to Business/Creator Account
1. Go to Instagram Settings -> Account -> Switch to Professional Account
2. Link to a Facebook Page (Instagram Settings -> Linked Accounts)

### 4. Get a Long-Lived Access Token
```bash
curl "https://graph.facebook.com/v19.0/oauth/access_token?grant_type=fb_exchange_token&client_id=YOUR_APP_ID&client_secret=YOUR_APP_SECRET&fb_exchange_token=SHORT_LIVED_TOKEN"
```
Tokens expire after 60 days. Re-run with a fresh short-lived token to renew.

### 5. Configure Webhooks
1. In your Developer App go to **Webhooks**
2. Set **Callback URL**: `https://your-domain.com/webhook/instagram`
3. Set **Verify Token**: must match your `WEBHOOK_VERIFY_TOKEN` env var
4. Subscribe to the `comments` field

### 6. Get Your Post ID
Use Graph API Explorer (https://developers.facebook.com/tools/explorer/):
```
GET /{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media?fields=id,caption,permalink
```

## Local Development

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # fill in your values
uvicorn main:app --reload --port 8000
```

For local webhook testing: `ngrok http 8000` then use the HTTPS URL as your Facebook webhook callback.

## Environment Variables

| Variable | Description |
|---|---|
| `INSTAGRAM_ACCESS_TOKEN` | Long-lived User Access Token (60-day expiry) |
| `INSTAGRAM_BUSINESS_ACCOUNT_ID` | Your Instagram Business Account ID |
| `FACEBOOK_APP_SECRET` | App Secret for webhook HMAC signature validation |
| `WEBHOOK_VERIFY_TOKEN` | Any random string matching your Facebook webhook config |
| `DATABASE_URL` | SQLAlchemy URL, defaults to `sqlite:///./app.db` |

## Deployment

### Railway
1. Push to GitHub, create a new project at https://railway.app
2. Railway auto-detects `Dockerfile` and `railway.toml`
3. Add env vars under Settings -> Variables

### Render
1. Create Web Service at https://render.com
2. Build: `pip install -r requirements.txt`
3. Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## DM Limitations

- **Before app review:** Only users who messaged your business first can receive DMs
- **After app review:** Can DM any commenter with approved `instagram_manage_messages`
- **24-hour rule:** Instagram only allows messaging within 24 hours of last user interaction
- **Rate limits:** Auto-retried with exponential backoff (up to 3 attempts on HTTP 429)

## Architecture

```
main.py              - FastAPI entry point, DB init
database.py          - SQLAlchemy engine + session
models.py            - Config, Campaign, ProcessedComment ORM models
instagram.py         - Async Graph API client with retry/backoff
routes/
  webhook.py         - GET/POST /webhook/instagram (verify + process)
  api.py             - REST API: /api/config, /api/campaigns/*
  dashboard.py       - Serves /dashboard HTML + /health
templates/
  dashboard.html     - Full SPA: dark theme, sidebar nav, modals
static/style.css     - Scrollbar + animation helpers
Dockerfile           - Production container
railway.toml         - Railway deployment config
```

## License

MIT
