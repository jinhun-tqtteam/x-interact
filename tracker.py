import json
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

import requests
from dotenv import load_dotenv

from twitter.scraper import Scraper  # from twitter-api-client

# ---------------------------------------------------------
# Config
# ---------------------------------------------------------

load_dotenv()


@dataclass
class Settings:
    cookies_file: str
    target_users: List[str]
    webhook_url: str
    poll_interval: int
    bootstrap_skip_initial: bool
    state_file: str = "tracker_state.json"


def get_settings() -> Settings:
    cookies_file = os.getenv("TWITTER_COOKIES_FILE", "twitter.cookies")

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

    return Settings(
        cookies_file=cookies_file,
        target_users=target_users,
        webhook_url=webhook_url,
        poll_interval=poll_interval,
        bootstrap_skip_initial=bootstrap_skip_initial,
    )


# ---------------------------------------------------------
# Simple local state (file-based)
# ---------------------------------------------------------

def load_state(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(path: str, data: Dict[str, Any]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ---------------------------------------------------------
# Twitter helpers (using Scraper)
# ---------------------------------------------------------

@dataclass
class TrackedUser:
    screen_name: str
    user_id: str
    display_name: Optional[str] = None


def init_scraper(settings: Settings) -> Scraper:
    """
    Khởi tạo Scraper bằng cookies.
    Đúng theo README: Scraper(cookies='twitter.cookies') hoặc cookies={"ct0":..., "auth_token":...}
    """
    if not os.path.exists(settings.cookies_file):
        raise RuntimeError(f"Cookies file not found: {settings.cookies_file}")

    scraper = Scraper(cookies=settings.cookies_file)
    return scraper


def resolve_users(scraper: Scraper, screen_names: List[str]) -> Dict[str, TrackedUser]:
    """
    Dùng scraper.users(...) để lấy thông tin user từ list screen_name.
    Shape exact của object tuỳ theo phiên bản twitter-api-client,
    nhưng đa phần sẽ có:
      - rest_id: id user
      - legacy.screen_name
      - legacy.name

    """
    print(f"[resolve_users] Resolving: {screen_names}")
    users = scraper.users(screen_names)
    resolved: Dict[str, TrackedUser] = {}

    # users thường là list các dict
    for u in users:
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

    # Warn nếu có user không resolve được
    unresolved = [
        s for s in screen_names if s.lower() not in resolved
    ]
    if unresolved:
        print(f"[resolve_users] WARNING: could not resolve users: {unresolved}")

    return resolved


def extract_tweet_core(tweet: Dict[str, Any], user: TrackedUser) -> Dict[str, Any]:
    """
    Chuẩn hoá tweet về payload đơn giản để bắn sang webhook.
    twitter-api-client thường trả về:
      - rest_id: id tweet
      - legacy.full_text
      - legacy.created_at
      - legacy.favorite_count, legacy.retweet_count, ...

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
        "raw": tweet,  # giữ full object nếu webhook cần
    }


def get_latest_tweets_for_user(
    scraper: Scraper,
    user: TrackedUser,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Lấy một số tweet mới nhất của user.
    API demo trong README là scraper.tweets([user_id])
    Ở đây ta gọi và normalize kết quả về dạng list tweet.
    """
    data = scraper.tweets([int(user.user_id)])

    # tuỳ phiên bản, data có thể là:
    # - list các tweet
    # - dict {user_id: [tweet, ...]}
    if isinstance(data, dict):
        # ưu tiên key = user_id; nếu không thì lấy list đầu tiên
        key = str(user.user_id)
        if key in data:
            tweets = data[key]
        else:
            # fallback: lấy value đầu tiên
            tweets = next(iter(data.values()))
    else:
        tweets = data

    if not isinstance(tweets, list):
        return []

    # sort theo id / created_at nếu cần; ở đây cứ assume tweets đã từ mới -> cũ
    return tweets[:limit]


# ---------------------------------------------------------
# Webhook
# ---------------------------------------------------------

def send_webhook(settings: Settings, payload: Dict[str, Any]) -> None:
    try:
        resp = requests.post(settings.webhook_url, json=payload, timeout=10)
        if resp.status_code >= 300:
            print(
                f"[webhook] Non-2xx status: {resp.status_code} - {resp.text[:200]}"
            )
    except Exception as e:
        print(f"[webhook] Error sending: {e}")


# ---------------------------------------------------------
# Main loop
# ---------------------------------------------------------

def main():
    settings = get_settings()
    print(f"[config] Tracking users: {settings.target_users}")
    print(f"[config] Poll interval: {settings.poll_interval}s")

    # load previous state
    state = load_state(settings.state_file)
    # state shape: { "<screen_name_lower>": { "last_tweet_id": "1234567890" } }

    scraper = init_scraper(settings)
    tracked_users = resolve_users(scraper, settings.target_users)

    if not tracked_users:
        raise RuntimeError("No users resolved, aborting.")

    print("[main] Resolved users:")
    for u in tracked_users.values():
        print(f"  - @{u.screen_name} (id={u.user_id}, name={u.display_name})")

    # Nếu bootstrap_skip_initial = true, lần chạy đầu chỉ set mốc last_tweet_id
    if settings.bootstrap_skip_initial and not state:
        print("[bootstrap] First run with BOOTSTRAP_SKIP_INITIAL=true → set baseline only.")
        for key, user in tracked_users.items():
            tweets = get_latest_tweets_for_user(scraper, user, limit=1)
            if tweets:
                core = extract_tweet_core(tweets[0], user)
                if core["tweet_id"]:
                    state[key] = {"last_tweet_id": core["tweet_id"]}
                    print(f"  Set baseline @{user.screen_name} → {core['tweet_id']}")
        save_state(settings.state_file, state)
        print("[bootstrap] Baseline saved. Next runs will emit only new tweets.")

    # Main polling loop
    print("[main] Starting polling loop...")
    while True:
        try:
            for key, user in tracked_users.items():
                user_state = state.get(key, {})
                last_seen_id_str = user_state.get("last_tweet_id")
                last_seen_id = int(last_seen_id_str) if last_seen_id_str else None

                tweets = get_latest_tweets_for_user(scraper, user, limit=5)
                if not tweets:
                    continue

                # Chuẩn hoá + sort từ cũ -> mới để bắn webhook đúng thứ tự
                normalized = []
                for t in tweets:
                    core = extract_tweet_core(t, user)
                    if not core["tweet_id"]:
                        continue
                    try:
                        tid_int = int(core["tweet_id"])
                    except ValueError:
                        continue
                    core["_tid_int"] = tid_int
                    normalized.append(core)

                normalized.sort(key=lambda x: x["_tid_int"])

                new_tweets = []
                for core in normalized:
                    tid_int = core["_tid_int"]
                    if last_seen_id is None or tid_int > last_seen_id:
                        new_tweets.append(core)

                if new_tweets:
                    print(f"[{user.screen_name}] Found {len(new_tweets)} new tweet(s).")
                    for core in new_tweets:
                        # bắn webhook
                        payload = {
                            "type": "tweet.new",
                            "source": "twitter-api-client-tracker",
                            "tweet": {
                                "tweet_id": core["tweet_id"],
                                "url": core["url"],
                                "full_text": core["full_text"],
                                "created_at": core["created_at"],
                                "metrics": core["metrics"],
                                "author": core["author"],
                            },
                        }
                        print(f"  -> sending {core['tweet_id']} to webhook")
                        send_webhook(settings, payload)

                        # update last_seen_id
                        last_seen_id = core["_tid_int"]
                        state[key] = {"last_tweet_id": str(last_seen_id)}

                    save_state(settings.state_file, state)

        except Exception as e:
            print(f"[main] Error in loop: {e}")

        time.sleep(settings.poll_interval)


if __name__ == "__main__":
    main()