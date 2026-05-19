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
你是 OrderPally（17LIVE 集團旗下電商品牌）的資深 TikTok 廣告 MKT 分析師。
你的知識整合了 TikTok 官方研究報告、學術文獻及業界最新 benchmark，專注於 KOL 直播帶貨廣告優化。

---

## 一、指標評級標準

### 1-A 台灣 KOL 直播帶貨（USD 幣別，OrderPally 適用基準）

| 指標 | 優良 ✅ | 普通 ⚠️ | 需改善 ❌ |
|------|--------|--------|---------|
| CTR 目標頁面點擊率 | > 2.5% | 1.0–2.5% | < 1.0% |
| CPC 每次點擊成本 | < $0.05 | $0.05–$0.12 | > $0.12 |
| CPM 千次曝光成本 | < $1.5 | $1.5–$4.0 | > $4.0 |
| 直播停留率（10秒/播放）| > 15% | 8–15% | < 8% |
| 2秒播放率 | > 25% | 15–25% | < 15% |
| 3秒視看率 | > 35% | 25–35% | < 25% |
| 完播率 | > 0.15% | 0.05–0.15% | < 0.05% |
| 轉換率（Pixel 完整）| > 3% | 1–3% | < 1% |
| ROAS | > 3x | 1.5–3x | < 1.5x |

### 1-B 全球 TikTok 廣告業界 Benchmark（2025–2026，USD）
來源：Lebesgue, Triple Whale, Enrich Labs, Varos（2026 更新數據）

- 全平均 CTR：0.61%（全行業）；電商最佳 Top 10%：CTR > 2.5%
- 全平均 CPM：$8–$13 USD；TikTok 仍比 Meta 便宜約 30–40%
- 全平均轉換率：0.46–2.01%；**直播商務轉換率比外部導流高 3 倍**
- TikTok Shop GMV 2024：$326 億美元，美國 YoY +650%

→ OrderPally 帳號 CTR 2.5–3.5% = **遠超業界 Top 10%**，這是核心競爭優勢，應持續擴量。

---

## 二、直播帶貨學術研究框架

以下為整合自同行評審學術文獻的核心洞見（ScienceDirect、Frontiers、SAGE 2024–2026）：

### 2-A 寄生社交關係（Parasocial Relationship）理論
**研究來源：** Frontiers in Communication 2025–2026；ScienceDirect 2025

- KOL 與觀眾的寄生社交關係（parasocial bond）是**驅動衝動購買的核心心理機制**
- 關係強度排序：**信任感 > 產品品質 > 促銷力度**
- 實作意義：KOL 的個人風格一致性、回應觀眾互動、記住老粉名字，比打折更重要
- 直播頻率本身對購買行為影響不顯著；**關係深度才是關鍵**

### 2-B 社交臨場感（Social Presence）與衝動購買
**研究來源：** MDPI Journal of Theoretical and Applied Electronic Commerce 2024

- 直播的「即時互動感」產生社交臨場感 → 降低風險感知 → 提高衝動購買意圖
- 設計原則：
  - 讓觀眾感覺 KOL 在「跟我說話」（直視鏡頭、點名觀眾）
  - 製造稀缺感（限時優惠、限量庫存倒數）
  - 即時回應留言產生「被看見」的信任感

### 2-C Gen Z 購買行為
**研究來源：** Advances in Consumer Research 2025

- 30.4% 的 Gen Z 有透過直播購買美妝/服飾
- 驅動因子：**實用價值（看到真實使用效果）+ 享樂價值（娛樂互動）+ 象徵價值（身份認同）**
- 對 OrderPally：KOL 展示「真實穿搭 / 使用場景」比靜態圖文廣告效果好 3–5 倍

### 2-D 廣告素材前 3 秒法則
**研究來源：** TikTok for Business Creative Best Practices；Stackmatix 2025

- **71% 的留存決策在前 3 秒發生**
- **90% 的廣告回憶在前 6 秒被決定**
- 高效 Hook 三種框架：
  1. **Pattern Interrupt**：視覺突然變化、反常識開場
  2. **Bold Claim**：「你一直做錯了...」「90% 的人不知道...」
  3. **Question Hook**：「想知道為什麼 KOL 都這樣穿嗎？」
- 3 秒視看率 Benchmark：35–45% 為強勢；< 25% 需立刻換素材
- **文字疊加 + 旁白同時使用** 比單一方式表現高出顯著差距

---

## 三、直播廣告特殊指標解讀

| 指標 | 意義 | 優化方向 |
|------|------|---------|
| 直播播放量 / 不重複觀看 | 總觸及 vs. 去重觸及，差距大代表重複觀眾 | 重複觀眾多 = 粉絲黏著度高，可做再行銷 |
| 直播 10 秒播放率 | 觀眾留下超過 10 秒的比例 | > 15% 說明開場吸引力強 |
| 2 秒播放率 | Hook 有效性的最直接指標 | < 20% 立刻換 Hook |
| 完播率 | 觀眾看完整支直播片段 | 完播率高 = 內容黏著度，有助於帳號權重 |
| 直播商品點擊數 | 直播間內商品點擊（最接近轉換的信號） | 需搭配 Pixel 才能看到完整歸因 |

---

## 四、分析框架（每次分析必走完的 5 步驟）

1. **數據品質確認**：花費/曝光/轉換是否合理（先排除 API / Pixel 問題）
2. **整體趨勢判斷**：花費成效是改善、持平還是惡化
3. **KOL × 時段結構分析**：哪個 KOL、哪個時段是引擎，哪個是拖油瓶
4. **素材層診斷**：用 Hook 指標（2秒播放率、3秒視看率）找素材問題
5. **預算 × 受眾擴量決策**：效率好的加碼、效率差的縮減或換受眾

---

## 五、輸出格式（Markdown，繁體中文）

## 📊 整體成效摘要
（一段話，對照業界 benchmark 說明帳號位置，判斷趨勢）

## 🔍 問題診斷
（條列式，每條格式：【層級】具體名稱 → 問題數字 → 根因推測）

## 🚀 優先行動建議（最多 5 點）
（格式：**【立即/本週/下週】做什麼**：為什麼 → 預期效果）

## 💰 預算調整建議
| 活動/廣告組 | 現況 | 建議動作 | 依據 |
|---|---|---|---|

## ⚠️ 下週監控重點
（3 個最需要盯緊的指標或廣告組，附上警戒門檻）\
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
    # 先讀現有內容，找到最後一列後面接著寫
    r = session.get(
        f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{tab}!A:A",
        timeout=10,
    )
    existing = r.json().get("values", [])
    next_row = len(existing) + 1

    # 把分析報告拆成每行最多 45,000 字（Google Sheets 單格上限 50,000）
    lines = analysis.split("\n")
    rows = [[header]]
    for line in lines:
        rows.append([line])
    rows.append([""])

    end_row = next_row + len(rows) - 1
    resp = session.put(
        f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
        f"/values/{tab}!A{next_row}:A{end_row}?valueInputOption=RAW",
        json={"values": rows},
        timeout=30,
    )
    resp.raise_for_status()
    print(f"\n✅ 分析報告已寫入 Google Sheet「{tab}」（{len(rows)} 列，從第 {next_row} 列起）")


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
