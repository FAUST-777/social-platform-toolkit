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

# 與 import_ads_csv.py 的 AD_HEADERS 完全一致（24 欄）
SHEET_HEADERS = [
    "日期",           # 1
    "廣告帳戶ID",     # 2  隱藏
    "活動ID",         # 3  隱藏
    "活動名稱",       # 4  隱藏
    "廣告組ID",       # 5  隱藏
    "廣告組名稱",     # 6  隱藏
    "廣告ID",         # 7
    "廣告名稱",       # 8
    "KOL",            # 9  ← 從廣告名稱解析
    "花費",           # 10
    "曝光次數",       # 11
    "點擊次數",       # 12
    "觸及人數",       # 13
    "點擊率(%)",      # 14
    "每次點擊成本",   # 15
    "每千次曝光成本", # 16
    "轉換次數",       # 17
    "每次轉換成本",   # 18
    "時段",           # 19 ← 從廣告名稱解析
    "直播播放量",     # 20 API 無此數據，留空
    "直播10秒播放",   # 21
    "2秒播放率(%)",   # 22
    "6秒播放率(%)",   # 23
    "完播率(%)",      # 24
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


def _parse_kol(name: str) -> str:
    import re
    m = re.search(r"[早中午晚]場[\s\-－]+(.+)", name.strip())
    return m.group(1).strip() if m else ""


def _parse_slot(name: str) -> str:
    import re
    m = re.search(r"([早中午晚]場)", name.strip())
    return m.group(1) if m else ""


def to_sheet_row(advertiser_id: str, item: dict) -> list:
    dim = item.get("dimensions", {})
    met = item.get("metrics", {})
    # 日期去掉時間部分（API 回傳 "2026-05-01 00:00:00"）
    raw_date = dim.get("stat_time_day", "")
    date_only = raw_date.split(" ")[0] if " " in raw_date else raw_date
    ad_name = met.get("ad_name", "")
    return [
        date_only,                          # 1  日期
        advertiser_id,                       # 2  廣告帳戶ID
        dim.get("campaign_id", ""),          # 3  活動ID
        met.get("campaign_name", ""),        # 4  活動名稱
        dim.get("adgroup_id", ""),           # 5  廣告組ID
        met.get("adgroup_name", ""),         # 6  廣告組名稱
        dim.get("ad_id", ""),               # 7  廣告ID
        ad_name,                            # 8  廣告名稱
        _parse_kol(ad_name),                # 9  KOL
        met.get("spend", ""),               # 10 花費
        met.get("impressions", ""),         # 11 曝光次數
        met.get("clicks", ""),              # 12 點擊次數
        met.get("reach", ""),               # 13 觸及人數
        met.get("ctr", ""),                 # 14 點擊率(%)
        met.get("cpc", ""),                 # 15 每次點擊成本
        met.get("cpm", ""),                 # 16 每千次曝光成本
        met.get("conversion", ""),          # 17 轉換次數
        met.get("cost_per_conversion", ""), # 18 每次轉換成本
        _parse_slot(ad_name),               # 19 時段
        "",                                 # 20 直播播放量（API無）
        "",                                 # 21 直播10秒播放
        "",                                 # 22 2秒播放率(%)
        "",                                 # 23 6秒播放率(%)
        "",                                 # 24 完播率(%)
    ]


def _sheet_session(service_account_file: Path):
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2.service_account import Credentials
    creds = Credentials.from_service_account_file(
        service_account_file,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return AuthorizedSession(creds)


def update_cover_sheet(
    service_account_file: Path,
    sheet_id: str,
    start_date: str,
    end_date: str,
    row_count: int,
    advertiser_id: str = "",
) -> None:
    from datetime import datetime
    import zoneinfo
    now_tw = datetime.now(zoneinfo.ZoneInfo("Asia/Taipei")).strftime("%Y-%m-%d %H:%M:%S")
    s = _sheet_session(service_account_file)
    status_rows = [
        ["📊 OP實驗型-直播帶貨 TikTok 廣告數據"],
        [""],
        ["最後更新時間（台灣）", now_tw],
        ["資料區間", f"{start_date}  ~  {end_date}"],
        ["資料筆數", row_count],
        ["廣告帳戶 ID", advertiser_id],
        ["資料來源", "TikTok Marketing API"],
        [""],
        ["TikTok 頻道", "https://www.tiktok.com/@17shoptaiwan"],
        ["電商平台", "https://mokibuy.com/17shoptaiwan/event/store/cartList"],
    ]
    s.put(
        f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
        f"/values/safe cover!A1:B10?valueInputOption=RAW",
        json={"values": status_rows}, timeout=30,
    ).raise_for_status()
    print(f"✅ safe cover 更新完畢（{now_tw}）")


def write_to_sheet(
    service_account_file: Path,
    sheet_id: str,
    tab: str,
    rows: list[list],
) -> None:
    import urllib.parse
    s = _sheet_session(service_account_file)
    tab_enc = urllib.parse.quote(tab, safe="")

    # 讀取現有數據，建立去重 key（廣告ID + 日期）
    r_existing = s.get(
        f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{tab_enc}!A:X",
        timeout=15,
    )
    existing_vals = r_existing.json().get("values", [])
    existing_keys: set[str] = set()
    if len(existing_vals) > 1:
        hdrs = existing_vals[0]
        try:
            date_idx = hdrs.index("日期")
            ad_id_idx = hdrs.index("廣告ID")
            for row in existing_vals[1:]:
                if len(row) > max(date_idx, ad_id_idx):
                    existing_keys.add(f"{row[date_idx]}|{row[ad_id_idx]}")
        except ValueError:
            pass  # header 不符時不做去重

    # 過濾掉已存在的列（去重）
    SHEET_HEADER_LIST = SHEET_HEADERS
    try:
        date_col = SHEET_HEADER_LIST.index("日期")
        adid_col = SHEET_HEADER_LIST.index("廣告ID")
    except ValueError:
        date_col, adid_col = 0, 6

    new_rows = []
    dup_count = 0
    for row in rows:
        key = f"{row[date_col]}|{row[adid_col]}"
        if key in existing_keys:
            dup_count += 1
        else:
            new_rows.append(row)
            existing_keys.add(key)

    if dup_count > 0:
        print(f"  ⚠️  去重：跳過 {dup_count} 筆已存在的紀錄，新增 {len(new_rows)} 筆")

    # 確認 header（24 欄）
    if not existing_vals or existing_vals[0] != SHEET_HEADERS:
        s.put(
            f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
            f"/values/{tab_enc}!A1:X1?valueInputOption=RAW",
            json={"values": [SHEET_HEADERS]}, timeout=15,
        ).raise_for_status()

    if new_rows:
        s.post(
            f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
            f"/values/{tab_enc}!A:X:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS",
            json={"values": new_rows},
            timeout=30,
        ).raise_for_status()


def write_to_csv(rows: list[list], days: int) -> Path:
    import csv as csv_module
    reports_dir = Path(__file__).parent.parent / "reports"
    reports_dir.mkdir(exist_ok=True)
    today = date.today().strftime("%Y-%m-%d")
    csv_path = reports_dir / f"tiktok_ads_{today}_last{days}days.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv_module.writer(f)
        writer.writerow(SHEET_HEADERS)
        writer.writerows(rows)
    return csv_path


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=1, help="拉最近 N 天（預設 1 = 昨天）")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--csv", action="store_true", help="同時輸出 CSV 到 reports/ 資料夾")
    parser.add_argument("--csv-only", action="store_true", help="只輸出 CSV，不寫 Google Sheet")
    args = parser.parse_args()

    # 支援從環境變數直接傳入 token（GitHub Actions 用）
    access_token = os.environ.get("TIKTOK_ACCESS_TOKEN")
    advertiser_ids_env = os.environ.get("TIKTOK_ADVERTISER_IDS")

    if not access_token:
        token_data = _token_store.load("advertiser")
        access_token = token_data["access_token"]
        advertiser_ids: list[str] = token_data.get("advertiser_ids", [])
    else:
        advertiser_ids = advertiser_ids_env.split(",") if advertiser_ids_env else []

    if not advertiser_ids:
        raise RuntimeError("advertiser_ids 為空，請確認授權帳號有廣告帳戶。")

    today = date.today()
    start_dt = today - timedelta(days=args.days)
    end_dt = today - timedelta(days=1)
    start_date = start_dt.strftime("%Y-%m-%d")
    end_date = end_dt.strftime("%Y-%m-%d")

    # TikTok API 單次最多 30 天，超過自動拆批
    MAX_DAYS = 30
    def date_chunks(start: date, end: date):
        cur = start
        while cur <= end:
            chunk_end = min(cur + timedelta(days=MAX_DAYS - 1), end)
            yield cur.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")
            cur = chunk_end + timedelta(days=1)

    all_rows: list[list] = []

    for advertiser_id in advertiser_ids:
        chunks = list(date_chunks(start_dt, end_dt))
        print(f"拉廣告帳戶 {advertiser_id}（{start_date} ~ {end_date}，共 {len(chunks)} 批）...")
        for c_start, c_end in chunks:
            items = fetch_report(access_token, advertiser_id, c_start, c_end)
            rows = [to_sheet_row(advertiser_id, item) for item in items]
            all_rows.extend(rows)
            print(f"  {c_start} ~ {c_end}：{len(rows)} 筆")
        print(f"  → 合計 {len(all_rows)} 筆")

    if args.dry_run:
        import json
        print(json.dumps(all_rows, ensure_ascii=False, indent=2))
        return

    if args.csv or args.csv_only:
        csv_path = write_to_csv(all_rows, args.days)
        print(f"已輸出 CSV → {csv_path}")

    if not args.csv_only:
        load_dotenv()
        sheet_id = os.environ["GOOGLE_SHEET_ID"]
        tab = os.environ.get("GOOGLE_SHEET_AD_TAB", "TikTok廣告成效")
        sa_file = Path(os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"])
        write_to_sheet(sa_file, sheet_id, tab, all_rows)
        print(f"\n已寫入 {len(all_rows)} 筆到 Google Sheet「{tab}」")
        update_cover_sheet(sa_file, sheet_id, start_date, end_date, len(all_rows), advertiser_ids[-1] if advertiser_ids else "")


if __name__ == "__main__":
    main()
