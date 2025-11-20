#!/usr/bin/env python3
"""
Script to help update Twitter cookies for X-Interact tracker
"""

import json
import os
from datetime import datetime

def update_cookies_in_accounts():
    """
    Cập nhật cookies mới vào file accounts.json
    """
    print("=" * 60)
    print("UPDATING TWITTER COOKIES FOR X-INTERACT")
    print("=" * 60)
    print()

    print("STEPS TO GET NEW COOKIES:")
    print("1. Mo trinh duyet va login vao https://twitter.com")
    print("2. Vao trang chinh Twitter de dam bao account khong bi locked")
    print("3. Mo Developer Tools (F12)")
    print("4. Di toi tab Application (Chrome) hoac Storage (Firefox)")
    print("5. Tim muc Cookies -> https://twitter.com")
    print("6. Tim va copy gia tri cua:")
    print("   - ct0 (csrf_token)")
    print("   - auth_token")
    print()

    ct0 = input("Nhap gia tri ct0: ").strip()
    auth_token = input("Nhap gia tri auth_token: ").strip()

    if not ct0 or not auth_token:
        print("Vui long nhap ca hai gia tri ct0 va auth_token!")
        return False

    # Đọc file accounts.json hiện tại
    accounts_file = "accounts.json"
    if not os.path.exists(accounts_file):
        print(f"Khong tim thay file {accounts_file}")
        return False

    try:
        with open(accounts_file, 'r', encoding='utf-8') as f:
            accounts_data = json.load(f)

        # Cập nhật cookies cho account đầu tiên
        if 'accounts' in accounts_data and len(accounts_data['accounts']) > 0:
            account = accounts_data['accounts'][0]
            old_ct0 = account.get('cookies', {}).get('ct0', 'N/A')
            old_auth = account.get('cookies', {}).get('auth_token', 'N/A')

            # Cập nhật cookies mới
            account['cookies'] = {
                'ct0': ct0,
                'auth_token': auth_token
            }

            # Reset health status
            account['health'] = {
                'is_healthy': True,
                'last_check': datetime.now().isoformat() + 'Z',
                'failed_count': 0,
                'last_success': datetime.now().isoformat() + 'Z'
            }

            # Backup file cu
            backup_file = f"{accounts_file}.backup"
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(accounts_data, f, indent=2, ensure_ascii=False)
            print(f"Da backup file cu thanh: {backup_file}")

            # Luu file moi
            with open(accounts_file, 'w', encoding='utf-8') as f:
                json.dump(accounts_data, f, indent=2, ensure_ascii=False)

            print()
            print("Cap nhat cookies thanh cong!")
            print(f"   Ten account: {account.get('name', 'N/A')}")
            print(f"   Old ct0: {old_ct0[:10]}..." if len(old_ct0) > 10 else f"   Old ct0: {old_ct0}")
            print(f"   New ct0: {ct0[:10]}..." if len(ct0) > 10 else f"   New ct0: {ct0}")
            print()
            print("Gio ban co the chay lai tracker.py")

        else:
            print("Khong tim thay account nao trong file accounts.json")
            return False

    except Exception as e:
        print(f"Loi khi cap nhat file: {e}")
        return False

    return True

def test_new_cookies():
    """
    Test cookies mới với Twitter API
    """
    print("\nTESTING NEW COOKIES...")

    try:
        from twitter.scraper import Scraper
        from twitter.util import init_session

        # Load accounts data
        with open('accounts.json', 'r', encoding='utf-8') as f:
            accounts_data = json.load(f)

        if 'accounts' in accounts_data and len(accounts_data['accounts']) > 0:
            account = accounts_data['accounts'][0]
            cookies = account.get('cookies', {})

            session = init_session()
            scraper = Scraper(session=session, cookies=cookies)

            # Test with a simple user lookup
            test_users = ['elonmusk']
            print(f"Testing with users: {test_users}")

            users = scraper.users(test_users)

            if users and len(users) > 0:
                user = users[0]
                if 'data' in user and 'user' in user['data'] and 'legacy' in user['data']['user']:
                    legacy = user['data']['user']['legacy']
                    print("Cookies hoat dong tot!")
                    print(f"   User: {legacy.get('screen_name', 'N/A')}")
                    print(f"   Name: {legacy.get('name', 'N/A')}")
                    print(f"   Followers: {legacy.get('followers_count', 'N/A')}")
                    return True
                else:
                    print("Response structure unexpected")
                    return False
            else:
                print("No response from API")
                return False

    except Exception as e:
        print(f"Test failed: {e}")
        return False

if __name__ == "__main__":
    # Update cookies
    if update_cookies_in_accounts():
        # Test new cookies
        if test_new_cookies():
            print("\nMoi thu da san sang! Chay tracker.py de bat dau.")
        else:
            print("\nCookies co the khong hop le, vui long kiem tra lai:")
            print("   - Account co dang bi lock khong?")
            print("   - Cookies co duoc copy dung khong?")