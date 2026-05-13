"""
TikTok Accounts API — 帳號授權（拉直播 / 影片 insights 用）

流程：
  1. 用瀏覽器前往以下 URL，完成 TikTok 帳號授權
  2. 授權成功後會跳到 Vercel callback 頁，複製 code
  3. 貼入此程式，換取 access_token + refresh_token

執行：python auth_account.py
"""
from __future__ import annotations

import os
import urllib.parse

import httpx
from dotenv import load_dotenv

import _token_store

ACCOUNTS_API = "https://open.tiktokapis.com/v2"
AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"

SCOPES = [
    "user.info.basic",
    "user.info.stats",
    "video.list",
]


def build_auth_url(client_key: str, redirect_uri: str) -> str:
    params = {
        "client_key": client_key,
        "scope": ",".join(SCOPES),
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": "orderpally_account",
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_token(client_key: str, client_secret: str, code: str, redirect_uri: str) -> dict:
    resp = httpx.post(
        f"{ACCOUNTS_API}/oauth/token/",
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"API error: {data.get('error_description', data['error'])}")
    return data


def refresh_token(client_key: str, client_secret: str, refresh_token_str: str) -> dict:
    resp = httpx.post(
        f"{ACCOUNTS_API}/oauth/token/",
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token_str,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    load_dotenv()
    app_id = os.environ["TIKTOK_APP_ID"]
    secret = os.environ["TIKTOK_APP_SECRET"]
    redirect_uri = os.environ["TIKTOK_ACCOUNT_REDIRECT_URI"]

    auth_url = build_auth_url(app_id, redirect_uri)
    print("\n=== TikTok Accounts API 授權 ===")
    print(f"\n1. 用瀏覽器開啟此 URL：\n\n   {auth_url}\n")
    print("2. 登入公司 TikTok 帳號並授權後，Vercel callback 頁會顯示 Authorization Code")
    print("3. 複製 Authorization Code 貼到下方\n")

    code = input("請貼入 code：").strip()
    if not code:
        print("code 不能為空")
        return

    print("\n換取 access_token 中...")
    token_data = exchange_token(app_id, secret, code, redirect_uri)

    _token_store.save("account", token_data)

    print("\n=== 授權成功 ===")
    print(f"  access_token : {token_data['access_token'][:20]}...")
    print(f"  open_id      : {token_data.get('open_id')}")
    print(f"  expires_in   : {token_data.get('expires_in')} 秒 ({token_data.get('expires_in', 0)//3600} 小時)")
    print(f"  scope        : {token_data.get('scope')}")
    print("\naccount_videos.py 和 main.py 現在可以直接執行了。")
    print("\n注意：access_token 有效期約 24 小時，到期後執行 python auth_account.py --refresh 即可。")


if __name__ == "__main__":
    import sys
    if "--refresh" in sys.argv:
        load_dotenv()
        app_id = os.environ["TIKTOK_APP_ID"]
        secret = os.environ["TIKTOK_APP_SECRET"]
        saved = _token_store.load("account")
        rt = saved.get("refresh_token")
        if not rt:
            print("找不到 refresh_token，請重新執行 auth_account.py 完整授權流程。")
            sys.exit(1)
        print("刷新 access_token 中...")
        new_data = refresh_token(app_id, secret, rt)
        saved.update(new_data)
        _token_store.save("account", saved)
        print(f"刷新成功，新 access_token: {new_data['access_token'][:20]}...")
    else:
        main()
