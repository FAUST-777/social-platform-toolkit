"""
TikTok Accounts API — 影片數據 → Google Sheet

拉公司 TikTok 帳號的最新影片清單及各項互動數據。

執行：
  python account_videos.py            # 最新 20 支影片
  python account_videos.py --count 50 # 最新 50 支
  python account_videos.py --dry-run  # 只印出，不寫 Sheet
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

import _token_store

ACCOUNTS_API = "https://open.tiktokapis.com/v2"

VIDEO_FIELDS = ",".join([
    "id",
    "create_time",
    "cover_image_url",
    "share_url",
    "video_description",
    "duration",
    "title",
    "like_count",
    "comment_count",
    "share_count",
    "view_count",
])

SHEET_HEADERS = [
    "抓取時間(UTC)",
    "影片ID",
    "標題",
    "說明",
    "發布時間(UTC)",
    "時長(秒)",
    "觀看次數",
    "按讚次數",
    "留言次數",
    "分享次數",
    "影片連結",
]


def fetch_videos(access_token: str, max_count: int = 20) -> list[dict]:
    headers = {"Authorization": f"Bearer {access_token}"}
    videos: list[dict] = []
    cursor: int | None = None

    while len(videos) < max_count:
        params: dict = {
            "fields": VIDEO_FIELDS,
            "max_count": min(20, max_count - len(videos)),
        }
        if cursor is not None:
            params["cursor"] = cursor

        resp = httpx.get(
            f"{ACCOUNTS_API}/video/list/",
            headers=headers,
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("error", {}).get("code") != "ok":
            err = data.get("error", {})
            raise RuntimeError(f"API error: {err.get('message')} ({err.get('code')})")

        batch = data.get("data", {}).get("videos", [])
        videos.extend(batch)

        if not data.get("data", {}).get("has_more") or not batch:
            break
        cursor = data["data"].get("cursor")

    return videos[:max_count]


def to_sheet_row(video: dict, collected_at: str) -> list:
    create_ts = video.get("create_time", 0)
    create_dt = (
        datetime.fromtimestamp(create_ts, tz=timezone.utc).isoformat(timespec="seconds")
        if create_ts
        else ""
    )
    return [
        collected_at,
        video.get("id", ""),
        video.get("title", ""),
        video.get("video_description", ""),
        create_dt,
        video.get("duration", ""),
        video.get("view_count", ""),
        video.get("like_count", ""),
        video.get("comment_count", ""),
        video.get("share_count", ""),
        video.get("share_url", ""),
    ]


def write_to_sheet(
    service_account_file: Path,
    sheet_id: str,
    tab: str,
    rows: list[list],
) -> None:
    creds = Credentials.from_service_account_file(
        service_account_file,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    service = build("sheets", "v4", credentials=creds)
    sheets = service.spreadsheets()

    range_check = f"{tab}!A1:K1"
    existing = sheets.values().get(spreadsheetId=sheet_id, range=range_check).execute()
    if not existing.get("values") or existing["values"][0] != SHEET_HEADERS:
        sheets.values().update(
            spreadsheetId=sheet_id,
            range=range_check,
            valueInputOption="RAW",
            body={"values": [SHEET_HEADERS]},
        ).execute()

    if rows:
        sheets.values().append(
            spreadsheetId=sheet_id,
            range=f"{tab}!A:K",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        ).execute()


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=20, help="拉幾支影片（預設 20）")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    token_data = _token_store.load("account")
    access_token = token_data["access_token"]
    open_id = token_data.get("open_id", "")

    print(f"拉 TikTok 帳號影片數據（open_id: {open_id}）...")
    videos = fetch_videos(access_token, args.count)
    print(f"  → 取得 {len(videos)} 支影片")

    collected_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = [to_sheet_row(v, collected_at) for v in videos]

    if args.dry_run:
        import json
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    sheet_id = os.environ["GOOGLE_SHEET_ID"]
    tab = os.environ.get("GOOGLE_SHEET_VIDEO_TAB", "TikTok影片數據")
    sa_file = Path(os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"])

    write_to_sheet(sa_file, sheet_id, tab, rows)
    print(f"已寫入 {len(rows)} 筆到 Google Sheet「{tab}」")


if __name__ == "__main__":
    main()
