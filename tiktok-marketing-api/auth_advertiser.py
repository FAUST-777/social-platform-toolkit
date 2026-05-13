"""
TikTok Marketing API — 廣告主授權

流程：
  1. 用瀏覽器前往以下 URL，完成 TikTok 授權
  2. 授權成功後會跳到 Vercel callback 頁，複製 auth_code
  3. 貼入此程式，換取 access_token

執行：python auth_advertiser.py
"""
from __future__ import annotations

import os
import urllib.parse

import httpx
from dotenv import load_dotenv

import _token_store

MARKETING_API = "https://business-api.tiktok.com/open_api/v1.3"
AUTH_URL = "https://ads.tiktok.com/marketing_api/auth"


def build_auth_url(app_id: str, redirect_uri: str) -> str:
    params = {
        "app_id": app_id,
        "redirect_uri": redirect_uri,
        "state": "orderpally_ads",
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_token(app_id: str, secret: str, auth_code: str) -> dict:
    resp = httpx.post(
        f"{MARKETING_API}/oauth2/access_token/",
        json={"app_id": app_id, "secret": secret, "auth_code": auth_code},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"API error {data.get('code')}: {data.get('message')}")
    return data["data"]


def main() -> None:
    load_dotenv()
    app_id = os.environ["TIKTOK_APP_ID"]
    secret = os.environ["TIKTOK_APP_SECRET"]
    redirect_uri = os.environ["TIKTOK_ADVERTISER_REDIRECT_URI"]

    auth_url = build_auth_url(app_id, redirect_uri)
    print("\n=== TikTok Marketing API 授權 ===")
    print(f"\n1. 用瀏覽器開啟此 URL：\n\n   {auth_url}\n")
    print("2. 登入並授權後，Vercel callback 頁會顯示 Authorization Code")
    print("3. 複製 Authorization Code 貼到下方\n")

    auth_code = input("請貼入 auth_code：").strip()
    if not auth_code:
        print("auth_code 不能為空")
        return

    print("\n換取 access_token 中...")
    token_data = exchange_token(app_id, secret, auth_code)

    _token_store.save("advertiser", token_data)

    print("\n=== 授權成功 ===")
    print(f"  access_token : {token_data['access_token'][:20]}...")
    print(f"  advertiser_ids: {token_data.get('advertiser_ids', [])}")
    print(f"  token_expiration_utc: {token_data.get('token_expiration_utc')}")
    print("\nad_reports.py 和 main.py 現在可以直接執行了。")


if __name__ == "__main__":
    main()
