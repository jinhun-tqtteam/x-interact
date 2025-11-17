# Twitter/X Tracker

A Python worker that tracks multiple X (Twitter) users and sends new tweets to a webhook in near real-time.

## Features

- Track multiple X users simultaneously
- Near real-time tweet detection (polling every X seconds)
- Send tweet data as JSON to webhook (n8n, custom server, etc.)
- Persistent state tracking to avoid duplicate notifications
- Bootstrap mode to skip initial tweets on first run

## ⚠️ Important Notes

- **Use a secondary account** for tracking - avoid using your main account
- Login using cookies (`ct0`, `auth_token`) as recommended
- This library uses **undocumented APIs** - there's a risk of rate limits or account suspension if you spam requests
- Be respectful with polling intervals

## Project Structure

```
twitter-tracker/
├── requirements.txt         # Python dependencies
├── .env.example            # Environment variables template
├── twitter.cookies.example # Cookie file template
├── tracker.py              # Main worker script
├── README.md               # This file
└── tracker_state.json      # State file (created automatically)
```

## Installation

1. Clone and setup the project:

```bash
git clone <repository-url>
cd twitter-tracker
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

### 1. Setup Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# File cookies JSON, chứa ct0 + auth_token
TWITTER_COOKIES_FILE=twitter.cookies

# Danh sách username cần track, cách nhau bởi dấu phẩy (không @)
TARGET_USERS=levelsio,yongfook,simonw

# Webhook nhận data tweet mới (n8n webhook URL)
WEBHOOK_URL=https://your-n8n-host/webhook/new-tweet

# Thời gian polling (giây)
POLL_INTERVAL_SECONDS=20

# true = lần chạy đầu chỉ set mốc, không bắn các tweet cũ
BOOTSTRAP_SKIP_INITIAL=true
```

### 2. Setup Twitter Cookies

1. Login to X/Twitter in your browser
2. Open browser developer tools (F12)
3. Go to Application/Storage → Cookies → x.com
4. Find and copy these two cookies:
   - `ct0`
   - `auth_token`

Create `twitter.cookies` file:

```bash
cp twitter.cookies.example twitter.cookies
```

Edit `twitter.cookies` with your actual cookie values:

```json
{
  "ct0": "your_ct0_cookie_value",
  "auth_token": "your_auth_token_value"
}
```

## Usage

Run the tracker:

```bash
python tracker.py
```

### How it works:

1. **First run** (if `BOOTSTRAP_SKIP_INITIAL=true`): Only sets baseline tweet IDs, doesn't send old tweets
2. **Subsequent runs**: Every `POLL_INTERVAL_SECONDS`, it will:
   - Fetch latest tweets for each tracked user
   - Compare with `last_tweet_id` from `tracker_state.json`
   - Send new tweets to the configured webhook URL

## Webhook Payload Format

The tracker sends JSON payloads in this format:

```json
{
  "type": "tweet.new",
  "source": "twitter-api-client-tracker",
  "tweet": {
    "tweet_id": "1988533975283880102",
    "url": "https://x.com/username/status/1988533975283880102",
    "full_text": "Tweet content here...",
    "created_at": "Wed Nov 12 09:06:59 +0000 2025",
    "metrics": {
      "like": 51,
      "retweet": 3,
      "reply": 4,
      "quote": 0
    },
    "author": {
      "user_id": "123456",
      "screen_name": "username",
      "name": "Display Name"
    }
  }
}
```

## Integration with n8n

In n8n, you can create workflows like:

`Webhook → Code/AI Agent → Telegram/X reply bot/RAG/Database`

The webhook endpoint should match the `WEBHOOK_URL` in your `.env` file.

## Troubleshooting

### Common Issues

1. **Cookie authentication issues**: Make sure your cookies are valid and not expired
2. **Rate limiting**: Increase `POLL_INTERVAL_SECONDS` if you encounter rate limits
3. **User resolution failures**: Verify usernames are correct and accounts are public
4. **Webhook failures**: Check that your webhook URL is accessible and can handle POST requests

### Logs

The script provides detailed logging for:
- Configuration loading
- User resolution
- Tweet detection
- Webhook sending
- Errors and warnings

## Dependencies

- `twitter-api-client==0.10.22` - Twitter API client
- `python-dotenv==1.0.1` - Environment variable management
- `requests==2.32.3` - HTTP requests for webhooks

## License

This project is provided as-is for educational and development purposes. Use responsibly and in accordance with Twitter's terms of service.