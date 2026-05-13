"""
TikTok 廣告後台 CSV 匯入工具

把從 TikTok Ads Manager 匯出的廣告組報表 CSV 整理後寫進 Google Sheet，
並自動建立「成效彙整」分析 tab。

使用方式：
  python import_ads_csv.py --csv ~/Downloads/你的報表.csv
  python import_ads_csv.py --csv ~/Downloads/你的報表.csv --summary-only  # 只重建彙整 tab
"""
from __future__ import annotations

import argparse
import csv
import os
import re
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import AuthorizedSession
from google.oauth2.service_account import Credentials

ADVERTISER_ID = "[REDACTED-ADVERTISER-ID]"

# 欄位順序依用戶自訂格式（KOL 在第9欄，時段在第19欄）
# 第 2-6 欄（廣告帳戶ID～廣告組名稱）寫入後會自動隱藏
AD_HEADERS = [
    "日期",        # 1  顯示
    "廣告帳戶ID",  # 2  隱藏
    "活動ID",      # 3  隱藏
    "活動名稱",    # 4  隱藏
    "廣告組ID",    # 5  隱藏
    "廣告組名稱",  # 6  隱藏
    "廣告ID",      # 7  顯示
    "廣告名稱",    # 8  顯示
    "KOL",         # 9  顯示 ← 移到此
    "花費",        # 10
    "曝光次數",    # 11
    "點擊次數",    # 12
    "觸及人數",    # 13
    "點擊率(%)",   # 14
    "每次點擊成本", # 15
    "每千次曝光成本", # 16
    "轉換次數",    # 17
    "每次轉換成本", # 18
    "時段",        # 19 ← 移到此
    "直播播放量",  # 20
    "直播10秒播放", # 21
    "2秒播放率(%)", # 22
    "6秒播放率(%)", # 23
    "完播率(%)",   # 24
]
# 寫入後要隱藏的欄索引（0-based）
_HIDDEN_COL_INDICES = [1, 2, 3, 4, 5]  # 廣告帳戶ID～廣告組名稱


def _session(sa_file: Path, readonly: bool = False) -> AuthorizedSession:
    scope = (
        "https://www.googleapis.com/auth/spreadsheets.readonly"
        if readonly
        else "https://www.googleapis.com/auth/spreadsheets"
    )
    creds = Credentials.from_service_account_file(sa_file, scopes=[scope])
    return AuthorizedSession(creds)


def safe(v: str) -> float:
    try:
        return float(str(v).replace(",", "").replace("%", "") or 0)
    except (ValueError, TypeError):
        return 0.0


def parse_date(name: str) -> str:
    m = re.match(r"(\d{8})", name.strip())
    if m:
        d = m.group(1)
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return ""


def parse_kol(name: str) -> str:
    m = re.search(r"[早中午晚]場[\s\-－]+(.+)", name.strip())
    return m.group(1).strip() if m else name.strip()


def parse_slot(name: str) -> str:
    m = re.search(r"([早中午晚]場)", name.strip())
    return m.group(1) if m else ""


def import_csv(csv_path: Path, session: AuthorizedSession, sheet_id: str) -> list[dict]:
    raw = list(csv.DictReader(open(csv_path, encoding="utf-8-sig")))
    rows = [r for r in raw if re.match(r"\d{8}", r.get("广告组名称", "").strip())]

    sheet_rows = [AD_HEADERS]
    for r in rows:
        name = r["广告组名称"].strip()
        clicks = safe(r["点击量（目标页面）"])
        ctr = safe(r["点击率（目标页面）"])
        spend = safe(r["消耗"])
        impr = int(clicks / (ctr / 100)) if ctr > 0 else 0
        cpm = round(spend / impr * 1000, 2) if impr > 0 else 0
        conv = int(safe(r.get("直播商品点击数", 0)))
        cpa = round(spend / conv, 2) if conv > 0 else 0

        sheet_rows.append([
            parse_date(name),               # 1  日期
            ADVERTISER_ID,                  # 2  廣告帳戶ID (隱藏)
            name, name, name, name,         # 3-6 活動ID/名稱/廣告組ID/名稱 (隱藏)
            r["广告名称"].strip(),           # 7  廣告ID
            r["广告名称"].strip(),           # 8  廣告名稱
            parse_kol(name),                # 9  KOL ← 第9欄
            spend,                          # 10 花費
            impr,                           # 11 曝光次數
            int(clicks),                    # 12 點擊次數
            int(safe(r.get("直播去重播放量", 0))),  # 13 觸及人數
            ctr,                            # 14 點擊率(%)
            safe(r["平均点击成本（目标页面）"]),  # 15 每次點擊成本
            cpm,                            # 16 每千次曝光成本
            conv,                           # 17 轉換次數
            cpa,                            # 18 每次轉換成本
            parse_slot(name),               # 19 時段 ← 第19欄
            int(safe(r.get("直播播放量", 0))),        # 20
            int(safe(r.get("直播播放 10 秒次数", 0))), # 21
            safe(r.get("2 秒播放率", 0)),   # 22
            safe(r.get("6 秒播放率", 0)),   # 23
            safe(r.get("视频完播率", 0)),   # 24
        ])

    tab = os.environ.get("GOOGLE_SHEET_AD_TAB", "TikTok廣告成效")
    session.put(
        f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{tab}!A1:X500?valueInputOption=RAW",
        json={"values": sheet_rows}, timeout=30
    ).raise_for_status()
    print(f"✅ 匯入 {len(sheet_rows)-1} 筆到「{tab}」")

    # 隱藏 ID 欄（廣告帳戶ID～廣告組名稱，第 2-6 欄，0-based index 1-5）
    r_info = session.get(
        f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}", timeout=10
    ).json()
    tab_sheet_id = next(
        sh["properties"]["sheetId"] for sh in r_info.get("sheets", [])
        if sh["properties"]["title"] == tab
    )
    hide_reqs = [
        {"updateDimensionProperties": {
            "range": {"sheetId": tab_sheet_id, "dimension": "COLUMNS",
                      "startIndex": i, "endIndex": i + 1},
            "properties": {"hiddenByUser": True},
            "fields": "hiddenByUser",
        }}
        for i in _HIDDEN_COL_INDICES
    ]
    session.post(
        f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}:batchUpdate",
        json={"requests": hide_reqs}, timeout=15,
    ).raise_for_status()
    print("  └ 已隱藏 ID 欄（廣告帳戶ID～廣告組名稱）")

    # 讀回乾淨數據（排除壞列）
    r_back = session.get(
        f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{tab}!A:X", timeout=15
    ).json().get("values", [])
    hdrs = r_back[0]
    return [
        dict(zip(hdrs, row + [""] * (len(hdrs) - len(row))))
        for row in r_back[1:]
        if row and row[0].startswith("2026")
    ]


def build_summary(data: list[dict], session: AuthorizedSession, sheet_id: str) -> None:
    def agg(rows: list[dict]) -> tuple:
        spend = sum(safe(r["花費"]) for r in rows)
        clicks = sum(safe(r["點擊次數"]) for r in rows)
        impr = sum(safe(r["曝光次數"]) for r in rows)
        lv = sum(safe(r["直播播放量"]) for r in rows)
        lu = sum(safe(r["觸及人數"]) for r in rows)
        ctr = round(clicks / impr * 100, 2) if impr > 0 else 0
        cpc = round(spend / clicks, 3) if clicks > 0 else 0
        return spend, int(clicks), int(impr), ctr, cpc, int(lv), int(lu)

    kol_d: dict = defaultdict(list)
    slot_d: dict = defaultdict(list)
    date_d: dict = defaultdict(list)
    for r in data:
        kol = r.get("KOL", "")
        if kol and not kol.replace(".", "").isdigit() and not kol.startswith("2026"):
            kol_d[kol].append(r)
        slot = r.get("時段", "")
        if slot:
            slot_d[slot].append(r)
        date = r.get("日期", "")
        if date:
            date_d[date].append(r)

    total = agg(data)
    sorted_ctr = sorted(data, key=lambda r: safe(r["點擊率(%)"]), reverse=True)
    SEP = [""] * 11

    content = [
        ["📊 TikTok 廣告成效彙整報告"],
        ["帳號", "舉手電商股份有限公司（永恆跨境數位2）", "", "廣告主ID", ADVERTISER_ID],
        ["廣告組數", len(data)],
        SEP,
        ["🔢 帳號總計"],
        ["總花費(USD)", "總點擊", "總曝光(估算)", "CTR(%)", "CPC(USD)", "直播播放量", "直播不重複觀看"],
        list(total),
        SEP,
        ["👑 KOL 成效排名（依 CTR 排序）"],
        ["KOL", "場次數", "總花費(USD)", "總點擊", "CTR(%)", "CPC(USD)", "直播播放量", "直播不重複觀看"],
    ]

    kol_rows = sorted(
        [(kol, len(rows), *agg(rows)) for kol, rows in kol_d.items()],
        key=lambda x: x[4], reverse=True,
    )
    for kol, cnt, sp, cl, im, ctr, cpc, lv, lu in kol_rows:
        content.append([kol, cnt, sp, cl, ctr, cpc, lv, lu])
    content.append(SEP)

    content += [
        ["⏰ 時段成效分析"],
        ["時段", "場次數", "總花費(USD)", "總點擊", "CTR(%)", "CPC(USD)", "直播播放量"],
    ]
    for slot in ["早場", "中場", "午場", "晚場"]:
        if slot not in slot_d:
            continue
        sp, cl, im, ctr, cpc, lv, lu = agg(slot_d[slot])
        content.append([slot, len(slot_d[slot]), sp, cl, ctr, cpc, lv])
    content.append(SEP)

    content += [
        ["📅 每日花費趨勢"],
        ["日期", "場次數", "花費(USD)", "點擊", "CTR(%)", "直播播放量"],
    ]
    for date in sorted(date_d.keys()):
        sp, cl, im, ctr, cpc, lv, lu = agg(date_d[date])
        content.append([date, len(date_d[date]), sp, cl, ctr, lv])
    content.append(SEP)

    content += [
        ["🏆 廣告組完整排名（依 CTR 高→低）"],
        ["排名", "日期", "廣告組名稱", "KOL", "時段", "花費(USD)", "CTR(%)", "CPC(USD)", "曝光(估算)", "點擊", "直播播放"],
    ]
    for i, r in enumerate(sorted_ctr, 1):
        content.append([
            i, r.get("日期", ""), r.get("活動名稱", ""), r.get("KOL", ""), r.get("時段", ""),
            safe(r["花費"]), safe(r["點擊率(%)"]), safe(r["每次點擊成本"]),
            int(safe(r["曝光次數"])), int(safe(r["點擊次數"])), int(safe(r["直播播放量"])),
        ])

    r_info = session.get(
        f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}", timeout=10
    ).json()
    sheet_ids = {sh["properties"]["title"]: sh["properties"]["sheetId"] for sh in r_info.get("sheets", [])}
    reqs = []
    if "成效彙整" in sheet_ids:
        reqs.append({"deleteSheet": {"sheetId": sheet_ids["成效彙整"]}})
    reqs.append({"addSheet": {"properties": {"title": "成效彙整", "index": 1}}})
    session.post(
        f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}:batchUpdate",
        json={"requests": reqs}, timeout=10,
    ).raise_for_status()

    session.put(
        f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/成效彙整!A1:K300?valueInputOption=RAW",
        json={"values": content}, timeout=30,
    ).raise_for_status()
    print(f"✅ 「成效彙整」tab 已建立，{len(data)} 筆數據")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="TikTok CSV 匯入工具")
    parser.add_argument("--csv", type=Path, help="CSV 檔案路徑")
    parser.add_argument("--summary-only", action="store_true", help="只重建成效彙整 tab")
    args = parser.parse_args()

    sa_file = Path(os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"])
    sheet_id = os.environ["GOOGLE_SHEET_ID"]
    session = _session(sa_file)

    if args.summary_only:
        tab = os.environ.get("GOOGLE_SHEET_AD_TAB", "TikTok廣告成效")
        r = session.get(
            f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{tab}!A:X", timeout=15
        ).json().get("values", [])
        hdrs = r[0]
        data = [
            dict(zip(hdrs, row + [""] * (len(hdrs) - len(row))))
            for row in r[1:]
            if row and row[0].startswith("2026")
        ]
        build_summary(data, session, sheet_id)
        return

    if not args.csv:
        print("請提供 --csv 檔案路徑，例如：python import_ads_csv.py --csv ~/Downloads/report.csv")
        return

    print(f"📥 匯入 {args.csv.name}...")
    data = import_csv(args.csv, session, sheet_id)
    build_summary(data, session, sheet_id)
    print("完成！")


if __name__ == "__main__":
    main()
