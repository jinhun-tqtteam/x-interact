# Twitter/X Multi-Account Tracker with Proxy Support

A Python worker that tracks multiple X (Twitter) users using multiple accounts with proxy support and sends new tweets to a webhook in near real-time.

## Features

- **Multi-account support** - Manage multiple Twitter accounts with automatic rotation
- **Proxy integration** - Each account can use its own proxy (HTTP/HTTPS/SOCKS5)
- **Smart rotation strategies** - Round-robin, random, or weighted account selection
- **Health monitoring** - Automatic proxy health checks and account status tracking
- **Rate limiting** - Per-account rate limiting to avoid API restrictions
- **Parallel processing** - Concurrent tweet fetching using multiple accounts
- **Failover handling** - Automatic account switching on failures
- **Near real-time detection** - Polling every X seconds
- **Persistent state tracking** - Avoid duplicate notifications
- **Bootstrap mode** - Skip initial tweets on first run

## ⚠️ Important Notes

- **Use secondary accounts** - Never use your main Twitter account
- **Proxy rotation recommended** - Distribute requests across different IP addresses
- **Rate limits apply** - Respect per-account and overall rate limits
- **Undocumented APIs** - Risk of rate limits or account suspension
- **Be responsible** - Use reasonable polling intervals

## Project Structure

```
twitter-tracker/
├── requirements.txt           # Python dependencies
├── .env.example              # Environment variables template
├── accounts.json.example     # Multi-account configuration template
├── accounts.json             # Your account configuration (create from example)
├── tracker.py                # Main worker script (multi-account support)
├── README.md                 # This file
└── tracker_state.json        # State file (created automatically)
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
# Account configuration file (JSON format)
ACCOUNTS_CONFIG=accounts.json

# Danh sách username cần track, cách nhau bởi dấu phẩy (không @)
TARGET_USERS=levelsio,yongfook,simonw

# Webhook nhận data tweet mới (n8n webhook URL)
WEBHOOK_URL=https://your-n8n-host/webhook/new-tweet

# Thời gian polling (giây)
POLL_INTERVAL_SECONDS=20

# true = lần chạy đầu chỉ set mốc, không bắn các tweet cũ
BOOTSTRAP_SKIP_INITIAL=true

# Account rotation strategy: round_robin, random, weighted
ACCOUNT_ROTATION_STRATEGY=round_robin

# Enable proxy rotation (true/false)
ENABLE_PROXY_ROTATION=true

# Proxy health check interval (giây)
PROXY_HEALTH_CHECK_INTERVAL=300

# Max failed requests before switching account
MAX_FAILED_REQUESTS_PER_ACCOUNT=3
```

### 2. Setup Multi-Account Configuration

Copy the example accounts configuration:

```bash
cp accounts.json.example accounts.json
```

Edit `accounts.json` with your account and proxy details:

```json
{
  "accounts": [
    {
      "id": "account_1",
      "name": "Primary Account",
      "enabled": true,
      "cookies": {
        "ct0": "your_ct0_cookie_for_account_1",
        "auth_token": "your_auth_token_for_account_1"
      },
      "proxy": {
        "enabled": true,
        "type": "http",
        "host": "proxy1.example.com",
        "port": 8080,
        "username": "proxy_user_1",
        "password": "proxy_pass_1"
      },
      "rate_limit": {
        "requests_per_minute": 30,
        "cooldown_minutes": 5
      }
    },
    {
      "id": "account_2",
      "name": "Secondary Account",
      "enabled": true,
      "cookies": {
        "ct0": "your_ct0_cookie_for_account_2",
        "auth_token": "your_auth_token_for_account_2"
      },
      "proxy": {
        "enabled": true,
        "type": "socks5",
        "host": "proxy2.example.com",
        "port": 1080,
        "username": "proxy_user_2",
        "password": "proxy_pass_2"
      },
      "rate_limit": {
        "requests_per_minute": 30,
        "cooldown_minutes": 5
      }
    }
  ],
  "global_settings": {
    "max_concurrent_accounts": 2,
    "account_cooldown_minutes": 15,
    "proxy_rotation_enabled": true,
    "health_check_interval_minutes": 5
  }
}
```

### 3. Getting Twitter Cookies

For each account you want to use:

1. Login to X/Twitter in your browser with that account
2. Open browser developer tools (F12)
3. Go to Application/Storage → Cookies → x.com
4. Find and copy these two cookies:
   - `ct0`
   - `auth_token`

5. Add them to the corresponding account in `accounts.json`

### 4. Proxy Setup (Recommended)

Each account can use its own HTTP proxy:

- **HTTP Proxy**: Standard HTTP proxy (supported)
- **Authentication**: Username/password supported
- **Per-account Session**: Each account uses separate session with its own proxy

Important notes:
- Only HTTP proxy is supported (SOCKS5 removed for simplicity)
- Each account gets its own session to avoid proxy conflicts
- Proxy configuration is applied per-account, not globally

Proxy providers recommended:
- Residential proxy services for better legitimacy
- Rotating proxy services for IP diversity
- Datacenter proxies (use with caution)

## Usage

Run the tracker:

```bash
python tracker.py
```

### How it works:

1. **Account Management**: Loads multiple accounts from `accounts.json` with their respective proxies
2. **Health Monitoring**: Continuously checks proxy health and account status
3. **Rotation Strategy**: Uses configured strategy (round_robin/random) to select accounts
4. **Parallel Processing**: Fetches tweets concurrently using multiple accounts
5. **Rate Limiting**: Respects per-account rate limits
6. **First run** (if `BOOTSTRAP_SKIP_INITIAL=true`): Only sets baseline tweet IDs, doesn't send old tweets
7. **Subsequent runs**: Every `POLL_INTERVAL_SECONDS`, it will:
   - Distribute users across available healthy accounts
   - Fetch latest tweets in parallel
   - Compare with `last_tweet_id` from `tracker_state.json`
   - Send new tweets to the configured webhook URL
   - Update account health status

## Webhook Payload Format

The multi-account tracker sends enhanced JSON payloads:

```json
{
  "type": "tweet.new",
  "source": "twitter-api-client-tracker-multi",
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
    },
    "source_account": {
      "account_id": "account_1",
      "account_name": "Primary Account"
    }
  }
}
```

Note the additional `source_account` field showing which account detected the tweet.

## Integration with n8n

In n8n, you can create workflows like:

`Webhook → Code/AI Agent → Telegram/X reply bot/RAG/Database`

The webhook endpoint should match the `WEBHOOK_URL` in your `.env` file.

## Advanced Configuration

### Account Rotation Strategies

1. **Round Robin**: Cycles through accounts evenly (default)
   ```env
   ACCOUNT_ROTATION_STRATEGY=round_robin
   ```

2. **Random**: Selects random healthy accounts
   ```env
   ACCOUNT_ROTATION_STRATEGY=random
   ```

### Rate Limiting

Per-account rate limiting prevents API restrictions:

```json
{
  "rate_limit": {
    "requests_per_minute": 30,    // Max requests per minute
    "cooldown_minutes": 5         // Cooldown after hitting limit
  }
}
```

### Proxy Configuration

HTTP proxy supported with per-account session management:

```json
{
  "proxy": {
    "enabled": true,
    "host": "proxy.example.com",
    "port": 8080,
    "username": "user",
    "password": "pass"
  }
}
```

Key features:
- **Per-account session**: Each account uses isolated session
- **No global environment variables**: Avoids proxy conflicts
- **Thread-safe**: Safe for concurrent processing

### Health Monitoring

Automatic health checks:
- **Proxy connectivity**: Tests proxy connections every 5 minutes (configurable)
- **Account status**: Tracks success/failure rates
- **Automatic failover**: Switches accounts on failures
- **Recovery**: Re-enables accounts after cooldown
- **Thread-safe updates**: Safe concurrent health tracking
- **Configurable failure threshold**: `MAX_FAILED_REQUESTS_PER_ACCOUNT` setting

## Troubleshooting

### Common Issues

1. **Account authentication issues**:
   - Verify cookies are valid and not expired
   - Check that accounts are not suspended
   - Ensure accounts have proper permissions

2. **Proxy connectivity problems**:
   - Test proxy connections manually
   - Verify proxy credentials
   - Check if proxy supports required protocols

3. **Rate limiting**:
   - Increase `POLL_INTERVAL_SECONDS`
   - Reduce `requests_per_minute` per account
   - Add more accounts to distribute load

4. **User resolution failures**:
   - Verify usernames are correct
   - Check if accounts are public
   - Ensure accounts have sufficient permissions

5. **Webhook failures**:
   - Check webhook URL accessibility
   - Verify POST request handling
   - Monitor webhook response codes

### Monitoring Logs

The script provides detailed logging for:
- Account loading and initialization
- Proxy health checks
- Account rotation and selection
- User resolution and tracking
- Tweet detection and processing
- Webhook delivery status
- Error recovery and failover

### Performance Optimization

1. **Concurrency**: Adjust `max_concurrent_accounts` based on your system capacity
2. **Polling intervals**: Balance between real-time detection and rate limits
3. **Proxy quality**: Use residential proxies for better legitimacy
4. **Account distribution**: Spread users across multiple accounts

## Dependencies

- `twitter-api-client==0.10.22` - Twitter API client
- `python-dotenv==1.0.1` - Environment variable management
- `requests==2.32.3` - HTTP requests for webhooks

## License

This project is provided as-is for educational and development purposes. Use responsibly and in accordance with Twitter's terms of service.