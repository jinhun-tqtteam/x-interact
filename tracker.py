import json
import os
import time
import random
import threading
import signal
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import deque
import queue

import requests
from dotenv import load_dotenv

from twitter.scraper import Scraper  # from twitter-api-client
from twitter.util import init_session

# ---------------------------------------------------------
# Config
# ---------------------------------------------------------

load_dotenv()


@dataclass
class Settings:
    accounts_config: str
    target_users: List[str]
    webhook_url: str
    poll_interval: int
    bootstrap_skip_initial: bool
    account_rotation_strategy: str
    enable_proxy_rotation: bool
    proxy_health_check_interval: int
    max_failed_requests_per_account: int
    state_file: str = "tracker_state.json"
    # New configurable values
    retry_delay_seconds: int = 2
    max_retry_delay_seconds: int = 30
    proxy_health_check_timeout: int = 10
    webhook_timeout: int = 10


def get_settings() -> Settings:
    accounts_config = os.getenv("ACCOUNTS_CONFIG", "accounts.json")

    target_raw = os.getenv("TARGET_USERS", "")
    target_users = [
        u.strip().lstrip("@")
        for u in target_raw.split(",")
        if u.strip()
    ]

    webhook_url = os.getenv("WEBHOOK_URL")
    if not webhook_url:
        raise RuntimeError("WEBHOOK_URL is required in .env")

    poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", "20"))
    bootstrap_skip_initial = os.getenv(
        "BOOTSTRAP_SKIP_INITIAL", "true"
    ).lower() == "true"

    account_rotation_strategy = os.getenv("ACCOUNT_ROTATION_STRATEGY", "round_robin")
    enable_proxy_rotation = os.getenv("ENABLE_PROXY_ROTATION", "true").lower() == "true"
    proxy_health_check_interval = int(os.getenv("PROXY_HEALTH_CHECK_INTERVAL", "300"))
    max_failed_requests_per_account = int(os.getenv("MAX_FAILED_REQUESTS_PER_ACCOUNT", "3"))
    
    # New configurable values with defaults
    retry_delay_seconds = int(os.getenv("RETRY_DELAY_SECONDS", "2"))
    max_retry_delay_seconds = int(os.getenv("MAX_RETRY_DELAY_SECONDS", "30"))
    proxy_health_check_timeout = int(os.getenv("PROXY_HEALTH_CHECK_TIMEOUT", "10"))
    webhook_timeout = int(os.getenv("WEBHOOK_TIMEOUT", "10"))

    return Settings(
        accounts_config=accounts_config,
        target_users=target_users,
        webhook_url=webhook_url,
        poll_interval=poll_interval,
        bootstrap_skip_initial=bootstrap_skip_initial,
        account_rotation_strategy=account_rotation_strategy,
        enable_proxy_rotation=enable_proxy_rotation,
        proxy_health_check_interval=proxy_health_check_interval,
        max_failed_requests_per_account=max_failed_requests_per_account,
        retry_delay_seconds=retry_delay_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
        proxy_health_check_timeout=proxy_health_check_timeout,
        webhook_timeout=webhook_timeout,
    )


# ---------------------------------------------------------
# Account Management
# ---------------------------------------------------------

@dataclass
class ProxyConfig:
    enabled: bool
    proxy_string: str = ""

    def to_dict(self) -> Dict[str, Any]:
        if not self.enabled or not self.proxy_string:
            return {}

        # Parse format: host:port:user:pass
        parts = self.proxy_string.split(':')
        if len(parts) < 4:
            return {}

        host, port, username, password = parts[0], parts[1], parts[2], ':'.join(parts[3:])

        proxy_url = f"http://{username}:{password}@{host}:{port}"

        return {
            "http": proxy_url,
            "https": proxy_url
        }


@dataclass
class RateLimit:
    requests_per_minute: int
    cooldown_minutes: int


@dataclass
class AccountHealth:
    is_healthy: bool = True
    last_check: str = ""
    failed_count: int = 0
    last_success: str = ""
    last_error: str = ""


@dataclass
class TwitterAccount:
    id: str
    name: str
    enabled: bool
    cookies: Dict[str, str]
    proxy: ProxyConfig
    rate_limit: RateLimit
    health: AccountHealth
    scraper: Optional[Scraper] = None
    request_times: deque = field(default_factory=lambda: deque(maxlen=100))  # Fixed memory leak
    lock: threading.Lock = field(default_factory=threading.Lock)
    scraper_lock: threading.Lock = field(default_factory=threading.Lock)  # For scraper access


class AccountManager:
    def __init__(self, config_path: str, max_failed_requests_per_account: int = 3):
        self.config_path = config_path
        self.accounts: Dict[str, TwitterAccount] = {}
        self.current_account_index = 0
        self.account_lock = threading.Lock()
        self.max_failed_requests_per_account = max_failed_requests_per_account
        self.state_lock = threading.Lock()  # For state file operations
        self.load_accounts()

    def load_accounts(self):
        """Load accounts from configuration file"""
        if not os.path.exists(self.config_path):
            raise RuntimeError(f"Accounts config file not found: {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        self.accounts = {}
        for acc_data in config.get("accounts", []):
            if not acc_data.get("enabled", True):
                continue

            proxy_data = acc_data.get("proxy", {})

            # Support both old format (dict) and new format (string)
            if isinstance(proxy_data, str):
                # New format: "host:port:user:pass"
                proxy = ProxyConfig(
                    enabled=True if proxy_data else False,
                    proxy_string=proxy_data
                )
            elif isinstance(proxy_data, dict):
                # Old format for backward compatibility
                enabled = proxy_data.get("enabled", False)
                if enabled:
                    host = proxy_data.get("host", "")
                    port = proxy_data.get("port", 0)
                    username = proxy_data.get("username", "")
                    password = proxy_data.get("password", "")
                    proxy_string = f"{host}:{port}:{username}:{password}" if host else ""
                else:
                    proxy_string = ""

                proxy = ProxyConfig(
                    enabled=enabled,
                    proxy_string=proxy_string
                )
            else:
                # No proxy
                proxy = ProxyConfig(enabled=False, proxy_string="")

            rate_limit_data = acc_data.get("rate_limit", {})
            rate_limit = RateLimit(
                requests_per_minute=rate_limit_data.get("requests_per_minute", 30),
                cooldown_minutes=rate_limit_data.get("cooldown_minutes", 5)
            )

            health_data = acc_data.get("health", {})
            health = AccountHealth(
                is_healthy=health_data.get("is_healthy", True),
                last_check=health_data.get("last_check", ""),
                failed_count=health_data.get("failed_count", 0),
                last_success=health_data.get("last_success", ""),
                last_error=health_data.get("last_error", "")
            )

            account = TwitterAccount(
                id=acc_data["id"],
                name=acc_data["name"],
                enabled=acc_data["enabled"],
                cookies=acc_data["cookies"],
                proxy=proxy,
                rate_limit=rate_limit,
                health=health
            )

            self.accounts[account.id] = account

        print(f"[account_manager] Loaded {len(self.accounts)} accounts")

    def save_accounts(self):
        """Save account health status back to config file"""
        if not os.path.exists(self.config_path):
            return

        with open(self.config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        for acc_data in config.get("accounts", []):
            acc_id = acc_data["id"]
            if acc_id in self.accounts:
                account = self.accounts[acc_id]
                acc_data["health"] = {
                    "is_healthy": account.health.is_healthy,
                    "last_check": account.health.last_check,
                    "failed_count": account.health.failed_count,
                    "last_success": account.health.last_success,
                    "last_error": account.health.last_error
                }

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def get_next_account(self, strategy: str = "round_robin") -> Optional[TwitterAccount]:
        """Get next available account based on strategy"""
        with self.account_lock:
            healthy_accounts = [acc for acc in self.accounts.values()
                              if acc.enabled and acc.health.is_healthy]

            if not healthy_accounts:
                print("[account_manager] No healthy accounts available")
                return None

            account = None
            if strategy == "round_robin":
                account = healthy_accounts[self.current_account_index % len(healthy_accounts)]
                self.current_account_index += 1
            elif strategy == "random":
                account = random.choice(healthy_accounts)
            else:
                account = healthy_accounts[0]
            
            return account

    def mark_account_success(self, account_id: str):
        """Mark account as successful"""
        if account_id in self.accounts:
            account = self.accounts[account_id]
            with account.lock:
                account.health.last_success = datetime.now().isoformat()
                account.health.failed_count = 0
                if not account.health.is_healthy:
                    account.health.is_healthy = True
                    print(f"[account_manager] Account {account.name} is now healthy")

    def mark_account_failure(self, account_id: str, error: str):
        """Mark account as failed"""
        if account_id in self.accounts:
            account = self.accounts[account_id]
            with account.lock:
                account.health.failed_count += 1
                account.health.last_error = error
                account.health.last_check = datetime.now().isoformat()

                max_failures = self.max_failed_requests_per_account
                if account.health.failed_count >= max_failures:
                    account.health.is_healthy = False
                    print(f"[account_manager] Account {account.name} marked as unhealthy after {account.health.failed_count} failures")

    def init_scraper(self, account: TwitterAccount) -> Scraper:
        """Initialize scraper for account with proxy support (per-account Session)"""
        with account.scraper_lock:  # Thread-safe scraper initialization
            if account.scraper is None:
                try:
                    # Create session with standard headers from twitter-api-client
                    session = init_session()

                    # httpx.Client already has built-in connection pooling and retries
                    # No need to configure adapter like requests.Session

                    # Apply proxy to session if enabled
                    if account.proxy.enabled:
                        proxy_dict = account.proxy.to_dict()
                        if proxy_dict:
                            # httpx uses different proxy configuration
                            session.proxies = proxy_dict
                            # httpx doesn't have trust_env option, but we can ensure it uses our proxy

                    # Initialize scraper with session + cookies
                    account.scraper = Scraper(
                        session=session,
                        cookies=account.cookies,
                    )

                    print(f"[account_manager] Initialized scraper for account {account.name} with proxy={account.proxy.enabled}")

                except Exception as e:
                    print(f"[account_manager] Failed to initialize scraper for {account.name}: {e}")
                    self.mark_account_failure(account.id, str(e))
                    raise

            return account.scraper

    def check_rate_limit(self, account: TwitterAccount) -> bool:
        """Check if account is within rate limits - O(1) with deque"""
        now = time.time()
        with account.lock:
            # Remove requests older than 1 minute (O(1) with deque)
            while account.request_times and now - account.request_times[0] >= 60:
                account.request_times.popleft()
            
            return len(account.request_times) < account.rate_limit.requests_per_minute

    def record_request(self, account: TwitterAccount):
        """Record a request timestamp for rate limiting"""
        with account.lock:
            account.request_times.append(time.time())


# ---------------------------------------------------------
# State Management
# ---------------------------------------------------------

def load_state(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(path: str, data: Dict[str, Any], lock: Optional[threading.Lock] = None) -> None:
    """Thread-safe state saving with optional lock"""
    if lock:
        with lock:
            _save_state_internal(path, data)
    else:
        _save_state_internal(path, data)

def _save_state_internal(path: str, data: Dict[str, Any]) -> None:
    """Internal state saving function"""
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception as e:
        print(f"[state] Error saving state to {path}: {e}")


# ---------------------------------------------------------
# Twitter helpers (using Scraper)
# ---------------------------------------------------------

@dataclass
class TrackedUser:
    screen_name: str
    user_id: str
    display_name: Optional[str] = None


def resolve_users_with_account(scraper: Scraper, screen_names: List[str], account: TwitterAccount) -> Dict[str, TrackedUser]:
    """
    Resolve users using specific account
    """
    print(f"[{account.name}] Resolving users: {screen_names}")

    try:
        users = scraper.users(screen_names)
        resolved: Dict[str, TrackedUser] = {}

        for u in users:
            # Handle new Twitter API response structure
            if "data" in u and "user" in u["data"] and "result" in u["data"]["user"]:
                result = u["data"]["user"]["result"]
                legacy = result.get("legacy", {})
                screen_name = (
                    legacy.get("screen_name")
                    or result.get("screen_name")
                    or result.get("username")
                )
                user_id = result.get("rest_id") or str(result.get("id") or "")
                name = legacy.get("name") or result.get("name")
            else:
                # Fallback to old structure
                legacy = u.get("legacy", {})
                screen_name = (
                    legacy.get("screen_name")
                    or u.get("screen_name")
                    or u.get("username")
                )
                user_id = u.get("rest_id") or str(u.get("id") or "")
                name = legacy.get("name") or u.get("name")

            if not screen_name or not user_id:
                continue

            key = screen_name.lower()
            resolved[key] = TrackedUser(
                screen_name=screen_name,
                user_id=str(user_id),
                display_name=name,
            )

        unresolved = [s for s in screen_names if s.lower() not in resolved]
        if unresolved:
            print(f"[{account.name}] WARNING: could not resolve users: {unresolved}")

        return resolved

    except Exception as e:
        print(f"[{account.name}] Error resolving users: {e}")
        raise


def extract_tweet_core(tweet: Dict[str, Any], user: TrackedUser, account: TwitterAccount) -> Dict[str, Any]:
    """
    Extract and normalize tweet data
    """
    legacy = tweet.get("legacy", {})

    tweet_id = (
        tweet.get("rest_id")
        or legacy.get("id_str")
        or tweet.get("id")
    )
    full_text = legacy.get("full_text") or legacy.get("text") or tweet.get("text")
    created_at = legacy.get("created_at")
    favorite_count = legacy.get("favorite_count")
    retweet_count = legacy.get("retweet_count")
    reply_count = legacy.get("reply_count")
    quote_count = legacy.get("quote_count")

    url = f"https://x.com/{user.screen_name}/status/{tweet_id}" if tweet_id else None

    return {
        "tweet_id": str(tweet_id) if tweet_id is not None else None,
        "url": url,
        "full_text": full_text,
        "created_at": created_at,
        "metrics": {
            "like": favorite_count,
            "retweet": retweet_count,
            "reply": reply_count,
            "quote": quote_count,
        },
        "author": {
            "user_id": user.user_id,
            "screen_name": user.screen_name,
            "name": user.display_name,
        },
        "source_account": {
            "account_id": account.id,
            "account_name": account.name,
        },
        "raw": tweet,
    }


def get_latest_tweets_for_user_with_account(
    scraper: Scraper,
    user: TrackedUser,
    account: TwitterAccount,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Get latest tweets for user using specific account
    """
    print(f"[{account.name}] Fetching tweets for @{user.screen_name}")

    try:
        # Validate user_id before converting to int
        try:
            user_id_int = int(user.user_id)
        except (ValueError, TypeError) as e:
            print(f"[{account.name}] Invalid user_id '{user.user_id}' for @{user.screen_name}: {e}")
            raise ValueError(f"Invalid user_id: {user.user_id}")
        
        data = scraper.tweets([user_id_int])

        if isinstance(data, dict):
            key = str(user.user_id)
            if key in data:
                tweets = data[key]
            else:
                tweets = next(iter(data.values()))
        else:
            tweets = data

        if not isinstance(tweets, list):
            return []

        return tweets[:limit]

    except Exception as e:
        print(f"[{account.name}] Error fetching tweets for @{user.screen_name}: {e}")
        raise


# ---------------------------------------------------------
# Webhook
# ---------------------------------------------------------

def send_webhook(settings: Settings, payload: Dict[str, Any]) -> None:
    try:
        resp = requests.post(settings.webhook_url, json=payload, timeout=settings.webhook_timeout)
        if resp.status_code >= 300:
            print(f"[webhook] Non-2xx status: {resp.status_code} - {resp.text[:200]}")
        else:
            print(f"[webhook] Successfully sent tweet {payload['tweet']['tweet_id']}")
    except Exception as e:
        print(f"[webhook] Error sending: {e}")


# ---------------------------------------------------------
# Proxy Health Check
# ---------------------------------------------------------

def check_proxy_health(account: TwitterAccount, timeout: int = 10) -> bool:
    """
    Check if proxy is working for the account
    """
    if not account.proxy.enabled:
        return True

    try:
        proxy_dict = account.proxy.to_dict()
        test_url = "https://httpbin.org/ip"

        response = requests.get(test_url, proxies=proxy_dict, timeout=timeout)
        if response.status_code == 200:
            print(f"[health_check] Proxy for {account.name} is working")
            return True
        else:
            print(f"[health_check] Proxy for {account.name} failed: HTTP {response.status_code}")
            return False

    except Exception as e:
        print(f"[health_check] Proxy for {account.name} failed: {e}")
        return False


def proxy_health_checker(account_manager: AccountManager, settings: Settings, shutdown_event: threading.Event):
    """
    Background thread to check proxy health periodically with graceful shutdown
    """
    while not shutdown_event.is_set():
        try:
            # Use wait with timeout to allow graceful shutdown
            if shutdown_event.wait(timeout=settings.proxy_health_check_interval):
                break
                
            for account in account_manager.accounts.values():
                if account.enabled and account.proxy.enabled:
                    is_healthy = check_proxy_health(account, settings.proxy_health_check_timeout)
                    if not is_healthy:
                        account_manager.mark_account_failure(account.id, "Proxy health check failed")
                    else:
                        account_manager.mark_account_success(account.id)

            account_manager.save_accounts()

        except Exception as e:
            print(f"[health_check] Error in health check: {e}")
            # Wait shorter time on error but still check shutdown event
            shutdown_event.wait(timeout=60)


# ---------------------------------------------------------
# Main tracking logic with multi-account support
# ---------------------------------------------------------

def process_user_tweets(
    user: TrackedUser,
    account_manager: AccountManager,
    settings: Settings,
    state: Dict[str, Any],
    result_queue: queue.Queue
):
    """
    Process tweets for a specific user using available accounts with exponential backoff
    """
    max_retries = 3
    base_delay = settings.retry_delay_seconds
    
    for attempt in range(max_retries):
        account = account_manager.get_next_account(settings.account_rotation_strategy)
        if not account:
            print(f"[{user.screen_name}] No available accounts")
            result_queue.put(("error", user.screen_name, "No available accounts", ""))
            break

        # Check rate limit
        if not account_manager.check_rate_limit(account):
            print(f"[{user.screen_name}] Account {account.name} rate limited, skipping")
            continue

        try:
            # Record request for rate limiting
            account_manager.record_request(account)

            # Initialize scraper if needed
            scraper = account_manager.init_scraper(account)

            # Get user state
            user_state = state.get(user.screen_name.lower(), {})
            last_seen_id_str = user_state.get("last_tweet_id")
            last_seen_id = int(last_seen_id_str) if last_seen_id_str else None

            # Fetch tweets
            tweets = get_latest_tweets_for_user_with_account(scraper, user, account, limit=5)
            if not tweets:
                result_queue.put(("success", user.screen_name, [], account.id))
                break

            # Process tweets
            normalized = []
            for t in tweets:
                core = extract_tweet_core(t, user, account)
                if not core["tweet_id"]:
                    continue
                try:
                    tid_int = int(core["tweet_id"])
                except ValueError:
                    continue
                core["_tid_int"] = tid_int
                normalized.append(core)

            normalized.sort(key=lambda x: x["_tid_int"])

            # Find new tweets
            new_tweets = []
            for core in normalized:
                tid_int = core["_tid_int"]
                if last_seen_id is None or tid_int > last_seen_id:
                    new_tweets.append(core)

            result_queue.put(("success", user.screen_name, new_tweets, account.id))

            # Mark account as successful
            account_manager.mark_account_success(account.id)
            break

        except Exception as e:
            print(f"[{user.screen_name}] Error with account {account.name} (attempt {attempt + 1}): {e}")
            account_manager.mark_account_failure(account.id, str(e))

            if attempt == max_retries - 1:
                result_queue.put(("error", user.screen_name, str(e), account.id))
            else:
                # Exponential backoff with jitter
                delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), settings.max_retry_delay_seconds)
                print(f"[{user.screen_name}] Retrying in {delay:.2f} seconds...")
                time.sleep(delay)


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    print(f"\n[main] Received signal {signum}, shutting down gracefully...")
    # Set global shutdown event
    if 'shutdown_event' in globals():
        shutdown_event.set()
    sys.exit(0)

def main():
    global shutdown_event
    shutdown_event = threading.Event()
    
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    settings = get_settings()
    print(f"[config] Tracking users: {settings.target_users}")
    print(f"[config] Poll interval: {settings.poll_interval}s")
    print(f"[config] Account rotation: {settings.account_rotation_strategy}")
    print(f"[config] Proxy rotation: {settings.enable_proxy_rotation}")

    # Initialize account manager
    account_manager = AccountManager(settings.accounts_config, settings.max_failed_requests_per_account)

    if not account_manager.accounts:
        raise RuntimeError("No enabled accounts found, aborting.")

    # Start proxy health checker if enabled
    health_thread = None
    if settings.enable_proxy_rotation:
        health_thread = threading.Thread(
            target=proxy_health_checker,
            args=(account_manager, settings, shutdown_event),
            daemon=True
        )
        health_thread.start()
        print("[main] Proxy health checker started")

    # Load previous state
    state = load_state(settings.state_file)

    # Resolve users using first available account
    tracked_users = {}
    for account in account_manager.accounts.values():
        if account.health.is_healthy:
            try:
                scraper = account_manager.init_scraper(account)
                tracked_users = resolve_users_with_account(scraper, settings.target_users, account)
                if tracked_users:
                    break
            except Exception as e:
                print(f"[main] Failed to resolve users with account {account.name}: {e}")
                continue

    if not tracked_users:
        raise RuntimeError("Failed to resolve users with any account, aborting.")

    print("[main] Resolved users:")
    for u in tracked_users.values():
        print(f"  - @{u.screen_name} (id={u.user_id}, name={u.display_name})")

    # Bootstrap mode
    if settings.bootstrap_skip_initial and not state:
        print("[bootstrap] First run with BOOTSTRAP_SKIP_INITIAL=true -> set baseline only.")
        for key, user in tracked_users.items():
            account = account_manager.get_next_account()
            if not account:
                continue

            try:
                scraper = account_manager.init_scraper(account)
                tweets = get_latest_tweets_for_user_with_account(scraper, user, account, limit=1)
                if tweets:
                    core = extract_tweet_core(tweets[0], user, account)
                    if core["tweet_id"]:
                        state[key] = {"last_tweet_id": core["tweet_id"]}
                        print(f"  Set baseline @{user.screen_name} → {core['tweet_id']}")
            except Exception as e:
                print(f"[bootstrap] Error setting baseline for @{user.screen_name}: {e}")

        save_state(settings.state_file, state, account_manager.state_lock)
        print("[bootstrap] Baseline saved. Next runs will emit only new tweets.")

    # Main polling loop with persistent thread pool
    print("[main] Starting multi-account polling loop...")
    
    # Create persistent thread pool to avoid recreation overhead
    max_workers = min(len(tracked_users), len(account_manager.accounts))
    executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="tweet-worker")

    try:
        while not shutdown_event.is_set():
            try:
                result_queue = queue.Queue()
                state_changed = False

                # Process users in parallel using persistent thread pool
                futures = []

                for user in tracked_users.values():
                    future = executor.submit(
                        process_user_tweets,
                        user,
                        account_manager,
                        settings,
                        state,
                        result_queue
                    )
                    futures.append(future)

                # Wait for all tasks to complete
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        print(f"[main] Error in future: {e}")

                # Process results with timeout to allow shutdown
                while not result_queue.empty():
                    try:
                        status, screen_name, data, account_id = result_queue.get_nowait()

                        if status == "success" and data:
                            user_key = screen_name.lower()

                            for core in data:
                                # Send webhook
                                payload = {
                                    "type": "tweet.new",
                                    "source": "twitter-api-client-tracker-multi",
                                    "tweet": {
                                        "tweet_id": core["tweet_id"],
                                        "url": core["url"],
                                        "full_text": core["full_text"],
                                        "created_at": core["created_at"],
                                        "metrics": core["metrics"],
                                        "author": core["author"],
                                        "source_account": core["source_account"],
                                    },
                                }
                                print(f"  -> sending {core['tweet_id']} from @{screen_name} to webhook")
                                send_webhook(settings, payload)

                                # Update state
                                state[user_key] = {"last_tweet_id": str(core["_tid_int"])}
                                state_changed = True

                        elif status == "error":
                            print(f"[main] Error processing @{screen_name}: {data}")

                    except queue.Empty:
                        break

                # Save state only if changed (reduces file I/O)
                if state_changed:
                    save_state(settings.state_file, state, account_manager.state_lock)

                # Save account health status (only if there were changes)
                account_manager.save_accounts()

            except Exception as e:
                print(f"[main] Error in main loop: {e}")

            # Use wait with timeout for graceful shutdown
            shutdown_event.wait(timeout=settings.poll_interval)

    finally:
        # Cleanup thread pool
        print("[main] Shutting down thread pool...")
        executor.shutdown(wait=True)
        
        # Wait for health thread to finish
        if health_thread and health_thread.is_alive():
            print("[main] Waiting for health checker to shutdown...")
            health_thread.join(timeout=5)
        
        print("[main] Shutdown complete")


if __name__ == "__main__":
    main()