#!/usr/bin/env python3
"""
Debug script to check actual tweet structure
"""
import json
from httpx import Client
from twitter.scraper import Scraper

print("=" * 60)
print("DEBUGGING TWEET STRUCTURE")
print("=" * 60)

# Load account
with open('accounts.json', 'r', encoding='utf-8') as f:
    acc = json.load(f)['accounts'][0]

# Setup proxy
proxy = None
pstr = acc.get('proxy')
if isinstance(pstr, str) and pstr:
    parts = pstr.split(':')
    if len(parts) >= 4:
        host, port, user, *rest = parts
        pwd = ':'.join(rest)
        proxy = f"http://{user}:{pwd}@{host}:{port}"

# Initialize session
session = Client(
    headers={
        "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
        "user-agent": "Mozilla/5.0",
    },
    follow_redirects=True,
    trust_env=False,
    proxy=proxy,
    timeout=30,
)

r = session.post('https://api.twitter.com/1.1/guest/activate.json')
guest = r.json().get('guest_token')
session.headers.update({
    "content-type": "application/json",
    "x-guest-token": guest,
    "x-twitter-active-user": "yes",
})

scraper = Scraper(session=session, cookies=acc['cookies'], save=False, pbar=False)

# Fetch tweets
user_id = 1761963877506363392
print(f"\nFetching tweets for user_id: {user_id}")
data = scraper.tweets([user_id], limit=5, save=False, pbar=False)

print(f"\n1. DATA TYPE: {type(data).__name__}")

# Parse data
if isinstance(data, dict):
    print(f"2. DATA KEYS: {list(data.keys())}")
    tweets = next(iter(data.values()))
else:
    tweets = data

print(f"3. TWEETS TYPE: {type(tweets).__name__}")
print(f"4. TWEETS LENGTH: {len(tweets) if isinstance(tweets, list) else 'N/A'}")

if isinstance(tweets, list) and len(tweets) > 0:
    tweet = tweets[0]
    print(f"\n5. FIRST TWEET KEYS: {list(tweet.keys())[:10]}")
    
    # Try different paths to extract tweet_id
    print("\n" + "=" * 60)
    print("TESTING TWEET_ID EXTRACTION:")
    print("=" * 60)
    
    # Method 1: rest_id
    rest_id = tweet.get("rest_id")
    print(f"1. tweet.get('rest_id'): {rest_id}")
    
    # Method 2: legacy.id_str
    legacy = tweet.get("legacy", {})
    id_str = legacy.get("id_str")
    print(f"2. tweet['legacy']['id_str']: {id_str}")
    
    # Method 3: id
    id_val = tweet.get("id")
    print(f"3. tweet.get('id'): {id_val}")
    
    # Method 4: Check if legacy exists
    print(f"\n4. Has 'legacy' key: {('legacy' in tweet)}")
    if 'legacy' in tweet:
        print(f"   Legacy keys: {list(legacy.keys())[:10]}")
    
    # Show full structure (limited)
    print("\n" + "=" * 60)
    print("FULL TWEET STRUCTURE (first 2000 chars):")
    print("=" * 60)
    tweet_json = json.dumps(tweet, indent=2, ensure_ascii=False)
    print(tweet_json[:2000])
    if len(tweet_json) > 2000:
        print(f"\n... (truncated, full size: {len(tweet_json)} chars)")
    
    # Extract text
    print("\n" + "=" * 60)
    print("TEXT EXTRACTION:")
    print("=" * 60)
    full_text = legacy.get("full_text") or legacy.get("text") or tweet.get("text")
    print(f"Text: {full_text[:200] if full_text else 'NOT FOUND'}")
    
    # Show what extract_tweet_core would return
    print("\n" + "=" * 60)
    print("WHAT EXTRACT_TWEET_CORE WOULD RETURN:")
    print("=" * 60)
    
    tweet_id = (
        tweet.get("rest_id")
        or legacy.get("id_str")
        or tweet.get("id")
    )
    
    result = {
        "tweet_id": str(tweet_id) if tweet_id is not None else None,
        "full_text": full_text,
        "has_valid_id": (tweet_id is not None and tweet_id != ""),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    if not result["has_valid_id"]:
        print("\n❌ PROBLEM FOUND!")
        print("   tweet_id is None or empty")
        print("   This is why state is not being saved")
        print("\n💡 SOLUTION:")
        print("   The tweet structure might be nested differently")
        print("   Checking for nested structure...")
        
        # Check for nested result
        if "data" in tweet or "tweet" in tweet or "result" in tweet:
            print("\n   Found nested structure!")
            print("   Keys:", list(tweet.keys()))
    else:
        print("\n✅ tweet_id extraction is working")
        print(f"   tweet_id: {result['tweet_id']}")
        
else:
    print("\n❌ No tweets found!")

print("\n" + "=" * 60)