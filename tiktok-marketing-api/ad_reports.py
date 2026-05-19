"""
TikTok Marketing API — 廣告成效報表 → Google Sheet

預設拉昨天的數據；可用 --days N 拉最近 N 天。

執行：
  python ad_reports.py              # 昨天
  python ad_reports.py --days 7    # 最近 7 天
  python ad_reports.py --dry-run   # 只印出，不寫 Sheet
"""
from __future__ import annotations

import argparse
import os
from datetime import date, timedelta
from pathlib import Path

import httpx
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

import _token_store

MARKETING_API = "https://business-api.tiktok.com/open_api/v1.3"

DIMENSIONS = ["stat_time_day", "campaign_id", "adgroup_id", "ad_id"]

METRICS = [
    "spend",
    "impressions",
    "clicks",
    "reach",
    "ctr",
    "cpc",
    "cpm",
    "conversion",
    "cost_per_conversion",
    "campaign_name",
    "adgroup_name",
    "ad_name",
]

SHEET_HEADERS = [
    "日期",
    "廣告帳戶ID",
    "活動ID",
    "活動名稱",
    "廣告組ID",
    "廣告組名稱",
    "廣告ID",
    "廣告名稱",
    "花費",
    "曝光次數",
    "點擊次數",
    "觸及人數",
    "點擊率(%)",
    "每次點擊成本",
    "每千次曝光成本",
    "轉換次數",
    "每次轉換成本",
]


def fetch_report(
    access_token: str,
    advertiser_id: str,
    start_date: str,
    end_date: str,
) -> list[dict]:
    headers = {"Access-Token": access_token}
    params = {
        "advertiser_id": advertiser_id,
        "report_type": "BASIC",
        "data_level": "AUCTION_AD",
        "dimensions": '["stat_time_day","ad_id"]',
        "metrics": "[" + ",".join('"' + m + '"' for m in METRICS) + "]",
        "start_date": start_date,
        "end_date": end_date,
        "page_size": 1000,
        "page": 1,
    }

    rows = []
    while True:
        resp = httpx.get(
            f"{MARKETING_API}/report/integrated/get/",
            headers=headers,
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            raise RuntimeError(f"API error {data.get('code')}: {data.get('message')}")

        page_data = data["data"]
        rows.extend(page_data.get("list", []))

        page_info = page_data.get("page_info", {})
        if page_info.get("page", 1) >= page_info.get("total_page", 1):
            break
        params["page"] += 1

    return rows


def to_sheet_row(advertiser_id: str, item: dict) -> list:
    dim = item.get("dimensions", {})
    met = item.get("metrics", {})
    return [
        dim.get("stat_time_day", ""),
        advertiser_id,
        dim.get("campaign_id", ""),
        met.get("campaign_name", ""),
        dim.get("adgroup_id", ""),
        met.get("adgroup_name", ""),
        dim.get("ad_id", ""),
        met.get("ad_name", ""),
        met.get("spend", ""),
        met.get("impressions", ""),
        met.get("clicks", ""),
        met.get("reach", ""),
        met.get("ctr", ""),
        met.get("cpc", ""),
        met.get("cpm", ""),
        met.get("conversion", ""),
        met.get("cost_per_conversion", ""),
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

    range_check = f"{tab}!A1:Q1"
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
            range=f"{tab}!A:Q",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        ).execute()


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=1, help="拉最近 N 天（預設 1 = 昨天）")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    token_data = _token_store.load("advertiser")
    access_token = token_data["access_token"]
    advertiser_ids: list[str] = token_data.get("advertiser_ids", [])

    if not advertiser_ids:
        raise RuntimeError("advertiser_ids 為空，請確認授權帳號有廣告帳戶。")

    today = date.today()
    start_date = (today - timedelta(days=args.days)).strftime("%Y-%m-%d")
    end_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")

    sheet_id = os.environ["GOOGLE_SHEET_ID"]
    tab = os.environ.get("GOOGLE_SHEET_AD_TAB", "TikTok廣告成效")
    sa_file = Path(os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"])

    all_rows: list[list] = []

    for advertiser_id in advertiser_ids:
        print(f"拉廣告帳戶 {advertiser_id} 的報表 ({start_date} ~ {end_date})...")
        items = fetch_report(access_token, advertiser_id, start_date, end_date)
        rows = [to_sheet_row(advertiser_id, item) for item in items]
        all_rows.extend(rows)
        print(f"  → {len(rows)} 筆")

    if args.dry_run:
        import json
        print(json.dumps(all_rows, ensure_ascii=False, indent=2))
        return

    write_to_sheet(sa_file, sheet_id, tab, all_rows)
    print(f"\n已寫入 {len(all_rows)} 筆到 Google Sheet「{tab}」")


if __name__ == "__main__":
    main()
