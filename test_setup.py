#!/usr/bin/env python3
"""
Script để test cookies và proxy trước khi chạy tracker
"""
import json
import time
from httpx import Client

# Load account config
with open('accounts.json', 'r', encoding='utf-8') as f:
    acc = json.load(f)['accounts'][0]

# Parse proxy
proxy = None
pstr = acc.get('proxy')
if isinstance(pstr, str) and pstr:
    parts = pstr.split(':')
    if len(parts) >= 4:
        host, port, user, *rest = parts
        pwd = ':'.join(rest)
        proxy = f"http://{user}:{pwd}@{host}:{port}"
        print(f"[proxy] Using proxy: {host}:{port}")
else:
    print("[proxy] No proxy configured")

# Test 1: Initialize session
print("\n=== TEST 1: Initialize Session ===")
try:
    session = Client(
        headers={
            "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
            "user-agent": "Mozilla/5.0",
        },
        follow_redirects=True,
        trust_env=False,
        proxy=proxy,
        timeout=10,  # Shorter timeout for testing
    )
    print("✓ Session created successfully")
except Exception as e:
    print(f"✗ Failed to create session: {e}")
    exit(1)

# Test 2: Get guest token
print("\n=== TEST 2: Get Guest Token ===")
try:
    r = session.post('https://api.twitter.com/1.1/guest/activate.json')
    print(f"  Status code: {r.status_code}")
    
    if r.status_code != 200:
        print(f"✗ Failed: {r.text[:200]}")
        if proxy:
            print("\n⚠ Proxy might be blocked by Twitter. Try:")
            print("  1. Test proxy without Twitter: curl -x <proxy> https://httpbin.org/ip")
            print("  2. Use a different proxy provider")
            print("  3. Disable proxy temporarily to test")
        exit(1)
    
    guest = r.json().get('guest_token')
    if guest:
        print(f"✓ Guest token: {guest[:20]}...")
    else:
        print("✗ No guest token in response")
        exit(1)
    
    session.headers.update({
        "content-type": "application/json",
        "x-guest-token": guest,
        "x-twitter-active-user": "yes",
    })
except Exception as e:
    print(f"✗ Error: {e}")
    print("\n⚠ This usually means:")
    print("  1. Proxy is not working")
    print("  2. Network connection issues")
    print("  3. Twitter API is blocking your requests")
    exit(1)

# Test 3: Test with cookies
print("\n=== TEST 3: Test Cookies ===")
try:
    from twitter.scraper import Scraper
    
    scraper = Scraper(
        session=session,
        cookies=acc['cookies'],
        save=False,
        pbar=False
    )
    print("✓ Scraper initialized with cookies")
except Exception as e:
    print(f"✗ Failed to initialize scraper: {e}")
    exit(1)

# Test 4: Fetch tweets (with timeout - Windows compatible)
print("\n=== TEST 4: Fetch Tweets ===")
test_user_id = 1761963877506363392  # jinhunkani
print(f"  Fetching tweets for user ID: {test_user_id}")
print("  This should take 5-10 seconds...")
print("  [Starting timer...]")

import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError

start_time = time.time()

def fetch_tweets():
    return scraper.tweets([test_user_id], limit=5, save=False, pbar=False)

try:
    # Use ThreadPoolExecutor with timeout (works on Windows)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fetch_tweets)
        
        try:
            # Wait max 15 seconds
            data = future.result(timeout=15)
            elapsed = time.time() - start_time
            print(f"  ⏱ Completed in {elapsed:.2f} seconds")
            
            # Parse result
            if isinstance(data, dict):
                tweets = next(iter(data.values()))
            else:
                tweets = data
            
            if isinstance(tweets, list) and len(tweets) > 0:
                print(f"✓ Successfully fetched {len(tweets)} tweets")
                print(f"  Latest tweet ID: {tweets[0].get('rest_id', 'N/A')}")
                tweet_text = tweets[0].get('legacy', {}).get('full_text', '')
                print(f"  Tweet preview: {tweet_text[:100]}...")
                print("\n✅ ALL TESTS PASSED! Your setup is working.")
                print("\n🎯 Next steps:")
                print("  1. Replace tracker.py with the fixed version")
                print("  2. Update your .env file with new settings")
                print("  3. Run: python tracker.py")
            else:
                print("✗ No tweets found or unexpected response format")
                print(f"  Data type: {type(data)}")
                print(f"  Data keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
                
        except TimeoutError:
            elapsed = time.time() - start_time
            print(f"✗ TIMEOUT after {elapsed:.2f} seconds")
            print("\n⚠ scraper.tweets() is HANGING - this is your problem!")
            print("\nPossible causes:")
            print("  1. Proxy is too slow or blocked by Twitter")
            print("  2. Cookies might be invalid (though guest token worked)")
            print("  3. Account is rate limited or suspended")
            print("  4. Twitter API is having issues")
            print("\n🔧 SOLUTIONS TO TRY:")
            print("  1. DISABLE PROXY temporarily:")
            print("     In accounts.json, change proxy to empty string:")
            print('     "proxy": ""')
            print("  2. GET FRESH COOKIES:")
            print("     python update_cookies.py")
            print("  3. TRY DIFFERENT PROXY:")
            print("     Your current proxy might be blacklisted by Twitter")
            print("  4. CHECK ACCOUNT STATUS:")
            print("     Login to Twitter manually to see if account is locked")
            
except Exception as e:
    elapsed = time.time() - start_time
    print(f"✗ Error after {elapsed:.2f} seconds: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*50)
print("DEBUG COMPLETE")
print("="*50)