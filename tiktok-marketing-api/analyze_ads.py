"""
TikTok 廣告 AI 行銷分析師

從 Google Sheet 讀取廣告成效數據，透過 Claude Opus 4.7 生成分析報告與行動建議。

執行：
  python analyze_ads.py                   # 分析最近 7 天
  python analyze_ads.py --days 14         # 分析最近 14 天
  python analyze_ads.py --dry-run         # 只印出彙整數據，不呼叫 Claude API
  python analyze_ads.py --output-sheet    # 分析結果也寫進 Google Sheet
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import date, timedelta
from pathlib import Path

import anthropic
import requests as req_lib
from dotenv import load_dotenv
from google.auth.transport.requests import AuthorizedSession
from google.oauth2.service_account import Credentials

MARKETING_EXPERT_SYSTEM = """\
你是 OrderPally（17LIVE 集團旗下電商品牌）的資深 TikTok 廣告成效分析師。
你深熟 TikTok for Business Marketing API、KOL 直播帶貨廣告、台灣/大中華區電商廣告投放策略。

## 指標評級標準（台灣 KOL 直播帶貨參考值，幣別 TWD）

| 指標 | 優良 | 普通 | 需改善 |
|------|------|------|--------|
| CTR 點擊率 | > 2.5% | 1.0–2.5% | < 1.0% |
| CPC 每次點擊成本 | < $8 | $8–$20 | > $20 |
| CPM 千次曝光成本 | < $150 | $150–$350 | > $350 |
| 轉換率 | > 3% | 1–3% | < 1% |
| 每次轉換成本 | < $200 | $200–$500 | > $500 |

## 分析框架
1. **整體趨勢**：花費與成效是否在改善、持平或惡化
2. **結構分析**：問題在哪一層（活動 / 廣告組 / 素材）
3. **優化機會**：找出成效最佳的廣告組，建議擴量
4. **淘汰候選**：找出成本過高或 CTR 極低的廣告組
5. **預算重分配**：具體的加減預算建議

## 輸出格式（Markdown，繁體中文）

## 📊 整體成效摘要
（一段話，附上關鍵數字，判斷整體趨勢）

## 🔍 問題診斷
（條列式，每條指出具體活動/廣告組名稱 + 問題數字 + 可能根因）

## 🚀 優先行動建議（最多 5 點）
（格式：**[做什麼]**：為什麼 → 預期效果）

## 💰 預算調整建議
| 活動/廣告組 | 目前花費佔比 | 建議動作 | 理由 |
|---|---|---|---|

## ⚠️ 下週監控重點
（3 個最需要盯緊的指標或廣告組）\
"""


def _authed_session(sa_file: Path, readonly: bool = True) -> AuthorizedSession:
    scope = (
        "https://www.googleapis.com/auth/spreadsheets.readonly"
        if readonly
        else "https://www.googleapis.com/auth/spreadsheets"
    )
    creds = Credentials.from_service_account_file(sa_file, scopes=[scope])
    return AuthorizedSession(creds)


def _read_sheet(sa_file: Path, sheet_id: str, tab: str) -> list[list[str]]:
    session = _authed_session(sa_file, readonly=True)
    url = (
        f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
        f"/values/{tab}!A:Q"
    )
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json().get("values", [])


def load_ad_data(sa_file: Path, sheet_id: str, tab: str, days: int) -> list[dict]:
    rows = _read_sheet(sa_file, sheet_id, tab)
    if not rows:
        return []
    headers, data_rows = rows[0], rows[1:]
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    records = []
    for row in data_rows:
        if len(row) < len(headers):
            row += [""] * (len(headers) - len(row))
        rec = dict(zip(headers, row))
        if rec.get("日期", "") >= cutoff:
            records.append(rec)
    return records


def aggregate(records: list[dict]) -> dict:
    def _num(v: str, cast=float) -> float | int:
        try:
            return cast(v or 0)
        except (ValueError, TypeError):
            return cast(0)

    campaigns: dict[str, dict] = {}
    for r in records:
        cid = r.get("活動ID", "")
        if cid not in campaigns:
            campaigns[cid] = {
                "名稱": r.get("活動名稱", cid),
                "花費": 0.0, "曝光": 0, "點擊": 0, "轉換": 0,
                "廣告組": {},
            }
        c = campaigns[cid]
        c["花費"] += _num(r.get("花費", 0))
        c["曝光"] += _num(r.get("曝光次數", 0), int)
        c["點擊"] += _num(r.get("點擊次數", 0), int)
        c["轉換"] += _num(r.get("轉換次數", 0), int)

        ag_id = r.get("廣告組ID", "")
        if ag_id and ag_id not in c["廣告組"]:
            c["廣告組"][ag_id] = {
                "名稱": r.get("廣告組名稱", ag_id),
                "花費": 0.0, "曝光": 0, "點擊": 0, "轉換": 0,
            }
        if ag_id:
            ag = c["廣告組"][ag_id]
            ag["花費"] += _num(r.get("花費", 0))
            ag["曝光"] += _num(r.get("曝光次數", 0), int)
            ag["點擊"] += _num(r.get("點擊次數", 0), int)
            ag["轉換"] += _num(r.get("轉換次數", 0), int)

    def metrics(d: dict) -> None:
        sp, imp, clk, conv = d["花費"], d["曝光"], d["點擊"], d["轉換"]
        d["CTR%"] = round(clk / imp * 100, 2) if imp else 0
        d["CPC"] = round(sp / clk, 1) if clk else 0
        d["CPM"] = round(sp / imp * 1000, 1) if imp else 0
        d["CPA"] = round(sp / conv, 1) if conv else 0

    total = {"花費": 0.0, "曝光": 0, "點擊": 0, "轉換": 0}
    for c in campaigns.values():
        metrics(c)
        for ag in c["廣告組"].values():
            metrics(ag)
        for k in ("花費", "曝光", "點擊", "轉換"):
            total[k] += c[k]
    metrics(total)

    return {"period_days": None, "總計": total, "活動": campaigns}


def run_analysis(data: dict, days: int) -> str:
    data["period_days"] = days
    payload = json.dumps(data, ensure_ascii=False, indent=2)

    user_msg = (
        f"以下是 OrderPally TikTok 廣告帳號最近 **{days} 天** 的成效數據（幣別：TWD）：\n\n"
        f"```json\n{payload}\n```\n\n"
        "請依照你的分析框架，提供詳細評估與具體行動建議。"
    )

    client = anthropic.Anthropic()
    print(f"\n🤖 行銷 AI 分析師分析中（最近 {days} 天）...\n" + "─" * 60 + "\n")

    full_text = ""
    with client.messages.stream(
        model="claude-opus-4-7",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=MARKETING_EXPERT_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            full_text += text

    print("\n" + "─" * 60)
    return full_text


def save_to_sheet(
    sa_file: Path, sheet_id: str, tab: str, analysis: str, days: int
) -> None:
    session = _authed_session(sa_file, readonly=False)
    header = f"=== {date.today().isoformat()} 分析（最近 {days} 天）==="
    url = (
        f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
        f"/values/{tab}!A:A:append"
        f"?valueInputOption=RAW&insertDataOption=INSERT_ROWS"
    )
    resp = session.post(
        url,
        json={"values": [[header], [analysis], [""]]},
        timeout=30,
    )
    resp.raise_for_status()
    print(f"\n✅ 分析報告已寫入 Google Sheet「{tab}」")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="TikTok 廣告 AI 行銷分析師")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-sheet", action="store_true")
    args = parser.parse_args()

    sheet_id = os.environ["GOOGLE_SHEET_ID"]
    ad_tab = os.environ.get("GOOGLE_SHEET_AD_TAB", "TikTok廣告成效")
    sa_file = Path(os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"])

    print(f"📥 讀取 Google Sheet「{ad_tab}」最近 {args.days} 天數據...")
    records = load_ad_data(sa_file, sheet_id, ad_tab, args.days)

    if not records:
        print("❌ 沒有找到數據。請先執行 ad_reports.py 拉取廣告數據。")
        return

    print(f"✅ 讀取到 {len(records)} 筆記錄，彙整中...")
    data = aggregate(records)

    if args.dry_run:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    analysis = run_analysis(data, args.days)

    if args.output_sheet:
        analysis_tab = os.environ.get("GOOGLE_SHEET_ANALYSIS_TAB", "TikTok行銷分析")
        save_to_sheet(sa_file, sheet_id, analysis_tab, analysis, args.days)


if __name__ == "__main__":
    main()
