"""
TikTok 廣告數據 QA Agent

自動核對：
1. Google Sheet 數據格式正確性
2. API 數據 vs Sheet 數據一致性
3. 欄位對齊、日期格式、數值合理性

執行：
  python qa_agent.py              # 核查最近 7 天
  python qa_agent.py --days 30    # 核查最近 30 天
  python qa_agent.py --output-sheet  # 結果寫進 TK大表「QA報告」tab
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import date, timedelta
from pathlib import Path

import anthropic
import httpx
from dotenv import load_dotenv
from google.auth.transport.requests import AuthorizedSession
from google.oauth2.service_account import Credentials

import _token_store

MARKETING_API = "https://business-api.tiktok.com/open_api/v1.3"

EXPECTED_HEADERS = [
    "日期", "廣告帳戶ID", "活動ID", "活動名稱", "廣告組ID", "廣告組名稱",
    "廣告ID", "廣告名稱", "KOL", "花費", "曝光次數", "點擊次數", "觸及人數",
    "點擊率(%)", "每次點擊成本", "每千次曝光成本", "轉換次數", "每次轉換成本",
    "時段", "直播播放量", "直播10秒播放", "2秒播放率(%)", "6秒播放率(%)", "完播率(%)",
]

QA_SYSTEM = """\
你是 OrderPally TikTok 廣告數據的 QA 工程師。
你的任務是核查 Google Sheet 數據的品質，找出以下問題：

1. **格式錯誤**：日期格式異常、數值為字串、欄位缺失
2. **邏輯異常**：CTR > 100%、點擊數 > 曝光數、花費為負數
3. **數據一致性**：Sheet 數據與 TikTok API 回傳是否對得上
4. **完整性**：有無遺漏某些日期、某些 KOL 的數據
5. **業務異常**：CTR 破萬%（可能是 API 歸因錯誤）、花費歸戶到空白活動

輸出格式（Markdown，繁體中文）：

## ✅ 通過檢查
（列出確認正確的項目）

## ⚠️ 警告（需注意但不緊急）
（條列，每條說明問題 + 涉及筆數）

## ❌ 嚴重問題（需立即處理）
（條列，每條說明問題 + 具體數值 + 建議修正方式）

## 📋 數據統計摘要
（總筆數、日期範圍、各 KOL 筆數、總花費）

## 🔧 建議修正行動
（優先順序排列）\
"""


def _sheet_session(sa_file: Path) -> AuthorizedSession:
    creds = Credentials.from_service_account_file(
        sa_file, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return AuthorizedSession(creds)


def read_sheet_data(sa_file: Path, sheet_id: str, tab: str, days: int) -> tuple[list[str], list[dict]]:
    s = _sheet_session(sa_file)
    import urllib.parse
    tab_enc = urllib.parse.quote(tab, safe="")
    r = s.get(f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{tab_enc}!A:X", timeout=15)
    rows = r.json().get("values", [])
    if not rows:
        return [], []
    headers = rows[0]
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    records = []
    for row in rows[1:]:
        if len(row) < 1:
            continue
        row_padded = row + [""] * (len(headers) - len(row))
        rec = dict(zip(headers, row_padded))
        if rec.get("日期", "") >= cutoff:
            records.append(rec)
    return headers, records


def fetch_api_sample(access_token: str, advertiser_id: str, days: int) -> list[dict]:
    """拉最近 7 天 API 數據作為對照樣本（避免超過 30 天限制）"""
    sample_days = min(days, 7)
    today = date.today()
    start = (today - timedelta(days=sample_days)).strftime("%Y-%m-%d")
    end = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    metrics = ["spend", "impressions", "clicks", "ctr", "conversion", "campaign_name", "ad_name"]
    params = {
        "advertiser_id": advertiser_id,
        "report_type": "BASIC",
        "data_level": "AUCTION_AD",
        "dimensions": '["stat_time_day","ad_id"]',
        "metrics": "[" + ",".join(f'"{m}"' for m in metrics) + "]",
        "start_date": start,
        "end_date": end,
        "page_size": 200,
        "page": 1,
    }
    resp = httpx.get(
        f"{MARKETING_API}/report/integrated/get/",
        headers={"Access-Token": access_token},
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        return []
    return data["data"].get("list", [])


def run_qa(headers: list[str], records: list[dict], api_sample: list[dict], days: int) -> str:
    """呼叫 Claude 做 QA 分析"""

    # 格式檢查（程式層）
    format_issues = []

    if headers != EXPECTED_HEADERS:
        missing = [h for h in EXPECTED_HEADERS if h not in headers]
        extra = [h for h in headers if h not in EXPECTED_HEADERS]
        if missing:
            format_issues.append(f"缺少欄位：{missing}")
        if extra:
            format_issues.append(f"多出欄位：{extra}")

    bad_dates = [r["日期"] for r in records if r.get("日期") and " " in r.get("日期", "")]
    high_ctr = [r for r in records if _safe_float(r.get("點擊率(%)")) > 100]
    click_gt_impr = [r for r in records if _safe_int(r.get("點擊次數")) > _safe_int(r.get("曝光次數")) > 0]
    zero_spend_with_clicks = [r for r in records if _safe_float(r.get("花費")) == 0 and _safe_int(r.get("點擊次數")) > 100]
    blank_kol = [r for r in records if not r.get("KOL") and r.get("花費") and _safe_float(r.get("花費")) > 0]

    # API vs Sheet 核對（比較最近 7 天花費總量）
    api_total_spend = sum(_safe_float(item.get("metrics", {}).get("spend", 0)) for item in api_sample)
    sheet_recent = [r for r in records if r.get("日期", "") >= (date.today() - timedelta(days=7)).isoformat()]
    sheet_total_spend = sum(_safe_float(r.get("花費", 0)) for r in sheet_recent)
    spend_diff_pct = abs(api_total_spend - sheet_total_spend) / max(api_total_spend, 0.01) * 100

    kol_counts: dict[str, int] = {}
    for r in records:
        kol = r.get("KOL", "(空白)")
        kol_counts[kol] = kol_counts.get(kol, 0) + 1

    summary = {
        "sheet_total_rows": len(records),
        "date_range_days": days,
        "headers_match": headers == EXPECTED_HEADERS,
        "format_issues": format_issues,
        "bad_date_format_count": len(bad_dates),
        "ctr_over_100_count": len(high_ctr),
        "clicks_gt_impressions_count": len(click_gt_impr),
        "zero_spend_high_clicks_count": len(zero_spend_with_clicks),
        "blank_kol_with_spend_count": len(blank_kol),
        "api_sample_spend_7d": round(api_total_spend, 2),
        "sheet_spend_7d": round(sheet_total_spend, 2),
        "spend_diff_pct": round(spend_diff_pct, 1),
        "kol_distribution": kol_counts,
        "sample_bad_rows": {
            "high_ctr": [{"日期": r.get("日期"), "廣告名稱": r.get("廣告名稱"), "CTR": r.get("點擊率(%)")} for r in high_ctr[:5]],
            "blank_kol": [{"日期": r.get("日期"), "廣告名稱": r.get("廣告名稱"), "花費": r.get("花費")} for r in blank_kol[:5]],
        },
    }

    client = anthropic.Anthropic()
    user_msg = (
        f"以下是 OrderPally TikTok廣告成效 Sheet 的 QA 核查結果（最近 {days} 天）：\n\n"
        f"```json\n{json.dumps(summary, ensure_ascii=False, indent=2)}\n```\n\n"
        "請根據這些數據，出具完整的 QA 報告。"
    )

    print("\n🔍 QA Agent 分析中...\n" + "─" * 60 + "\n")
    full_text = ""
    with client.messages.stream(
        model="claude-opus-4-7",
        max_tokens=3000,
        thinking={"type": "adaptive"},
        system=QA_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            full_text += text
    print("\n" + "─" * 60)
    return full_text


def _safe_float(v) -> float:
    try:
        return float(str(v).replace(",", "") or 0)
    except (ValueError, TypeError):
        return 0.0


def _safe_int(v) -> int:
    try:
        return int(float(str(v).replace(",", "") or 0))
    except (ValueError, TypeError):
        return 0


def save_qa_to_sheet(sa_file: Path, sheet_id: str, qa_text: str, days: int) -> None:
    from datetime import datetime
    import zoneinfo, urllib.parse
    s = _sheet_session(sa_file)
    now_tw = datetime.now(zoneinfo.ZoneInfo("Asia/Taipei")).strftime("%Y-%m-%d %H:%M:%S")
    tab = "QA報告"

    # 確認 QA報告 tab 存在，不存在就建立
    r_info = s.get(f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}", timeout=10).json()
    tabs = {sh["properties"]["title"]: sh["properties"]["sheetId"] for sh in r_info.get("sheets", [])}
    if tab not in tabs:
        s.post(
            f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}:batchUpdate",
            json={"requests": [{"addSheet": {"properties": {"title": tab}}}]},
            timeout=10,
        ).raise_for_status()

    tab_enc = urllib.parse.quote(tab, safe="")
    r = s.get(f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{tab_enc}!A:A", timeout=10)
    next_row = len(r.json().get("values", [])) + 1

    rows = [[f"=== QA 報告 {now_tw}（最近 {days} 天）==="]
            ] + [[line] for line in qa_text.split("\n")] + [[""]]

    s.put(
        f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
        f"/values/{tab_enc}!A{next_row}:A{next_row + len(rows)}?valueInputOption=RAW",
        json={"values": rows}, timeout=30,
    ).raise_for_status()
    print(f"\n✅ QA 報告已寫入 TK大表「{tab}」tab")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="TikTok 廣告數據 QA Agent")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--output-sheet", action="store_true")
    args = parser.parse_args()

    sa_file = Path(os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"])
    sheet_id = os.environ["GOOGLE_SHEET_ID"]
    ad_tab = os.environ.get("GOOGLE_SHEET_AD_TAB", "TikTok廣告成效")

    print(f"📥 讀取 TK大表「{ad_tab}」最近 {args.days} 天...")
    headers, records = read_sheet_data(sa_file, sheet_id, ad_tab, args.days)
    print(f"  → {len(records)} 筆")

    token_data = _token_store.load("advertiser")
    access_token = token_data["access_token"]
    advertiser_ids = token_data.get("advertiser_ids", [])

    print("📡 拉 TikTok API 樣本數據（最近 7 天）...")
    api_sample = []
    for adv_id in advertiser_ids:
        api_sample.extend(fetch_api_sample(access_token, adv_id, args.days))
    print(f"  → API 樣本 {len(api_sample)} 筆")

    qa_text = run_qa(headers, records, api_sample, args.days)

    if args.output_sheet:
        save_qa_to_sheet(sa_file, sheet_id, qa_text, args.days)


if __name__ == "__main__":
    main()
