# TikTok Hot Products Pipeline — 專案筆記

> 紀錄日期：2026-05-08（初版） / 2026-05-12（更新範圍）
> 用途：彙整 codex 建立的 `tiktok_threads_hot_products` 專案現況、檔案清單、設計、現存問題、與下一步。

---

## 📌 範圍決策（2026-05-12 更新）

| 平台 | 狀態 | 說明 |
|---|---|---|
| **TikTok** | ✅ **主力，集中開發** | 廣告投放成效 + KOL 直播表現，正式上線目標 |
| **Facebook / Meta** | ❌ **不做** | 放棄這條社群（既有 `meta_insights_pipeline.py` 不在本專案範圍內，獨立維護） |
| **Threads** | ⏸️ **暫緩** | 程式骨架保留，但近期不投入，之後再評估 |

### 🎯 TikTok 的實際需求（2026-05-12 確認）

**Goal A：廣告投放成效報表**
- 透過 TikTok Marketing API 拉自家廣告帳戶數據
- 寫進 Google Sheet → 後續做 Looker Studio 視覺化

**Goal B：KOL 直播效益追蹤**
- 公司有**1 個 TikTok 頻道**，多位 KOL 輪流上去開直播（KOL **不用自己帳號**）
- 商品買賣導到**其他電商平台**（非 TikTok Shop）
- 需要追蹤：觀看人數、停留時間、留言、分享、轉換等
- 數據來源分兩部分：
  - 付費推廣的部分 → Marketing API Reporting
  - 直播本身整體表現 → TikTok Accounts API（含自然觸及）

### 📋 TikTok App 申請 - 最終勾選清單

**主力 App 名稱**：`Jushou Ads Reporting`（或類似）

✅ 必勾權限：
- `Ad Account Management → Read Ad Account Information`
- `Ads Management → 全部 Read 子項`
- `Reporting → 全部 Read 報表`（含直播投放指標）
- `TikTok Accounts → 全部 Read`（拿公司 TikTok 帳號的直播數據）

❌ 不勾：
- Lead Management、DPA Catalog、TCM、Creative Management、Audience Management
- 任何 Write / Update / Create / Delete
- 任何 Pangle 相關
- 任何 BC 內部管理 API（`/bc/...`）

### ⚠️ 前提條件
- [ ] 公司 TikTok 帳號是 **Business Account**
- [ ] 公司 TikTok 帳號**已綁定**到 BC「舉手電商」
- [ ] 公司 TikTok 帳號已 **link** 到廣告帳戶
- [ ] Communication Email 用**公司網域**（上次申請被拒主因）
- [ ] Company Website 跟 Email 網域**相同**

**對程式碼的影響**：
- `CustomJsonSource` 保留（之後 Threads / 第三方資料商都可能用）
- `sources.yml` 的 `custom_json` 段保持 `enabled: false`
- 不需要刪除既有 Threads 相關註解或 README 段落（成本高、價值低）
- 後續所有開發資源、API 預算、排程都圍繞 TikTok

---

## 1. 專案位置與環境

| 項目 | 路徑 / 值 |
|---|---|
| 專案根目錄 | `/Users/willielin/tiktok_threads_hot_products` |
| 建立日期 | 2026-04-30（codex 一次性產生） |
| Python 版本要求 | `>=3.11` |
| 虛擬環境 | ❌ **尚未建立**（`.venv` 不存在） |
| Google service account 檔 | ❌ **尚未放置**（`service-account.json` 不存在） |
| 已綁定的 Google Sheet ID | `[REDACTED-SHEET-ID]` |
| Sheet 分頁 | `HotProducts` |
| Git 狀態 | 沒有 `.git`（尚未初始化版本控制） |

---

## 2. 完整檔案清單（21 個檔案）

```
tiktok_threads_hot_products/
├── .env                           # 已填入 GOOGLE_SHEET_ID
├── .env.example                   # 範本
├── .github/
│   └── workflows/
│       └── scheduled.yml          # 每 6 小時跑一次 (cron "0 */6 * * *")
├── .gitignore                     # 排除 .env / .venv / service-account.json / logs/
├── README.md                      # 中文說明（建置/設定/執行/排程）
├── config/
│   ├── sources.example.yml        # 範本
│   └── sources.yml                # 與 example 內容相同（尚未客製）
├── pyproject.toml                 # 套件設定 + entry point: hot-products
├── scripts/
│   └── run_once.sh                # 一鍵執行 wrapper
└── src/hot_products/
    ├── __init__.py                # version: 0.1.0
    ├── cli.py                     # argparse: hot-products run [--config] [--dry-run]
    ├── config.py                  # 讀 yaml
    ├── models.py                  # ProductSignal dataclass + SHEET_HEADERS
    ├── pipeline.py                # collect_signals / dedupe / write_signals
    ├── scoring.py                 # sold_count → 分數（含 K/M 後綴解析）
    ├── settings.py                # pydantic Settings（讀 .env）
    ├── sheets.py                  # GoogleSheetsWriter（ensure_header + append）
    └── sources/
        ├── __init__.py            # build_sources() 工廠函式
        ├── base.py                # ProductSource ABC
        ├── custom_json.py         # 通用 JSON endpoint 來源（給資料商接 API 用）
        └── tiktok_shop.py         # 公開頁爬蟲（115 行，已完整）
```

---

## 3. 架構設計概念

### 3.1 資料流

```
config/sources.yml ──┐
                     ├──> build_sources() ──> [ProductSource, ...]
.env (Settings) ─────┘                           │
                                                 ↓
                                           collect()  ── yield ProductSignal
                                                 │
                                                 ↓
                                    pipeline.collect_signals()
                                                 │
                                                 ↓ dedupe by (platform, url, name)
                                                 │
                                                 ↓
                              ┌────────── --dry-run ──> stdout JSON
                              │
                              └────────── default  ──> GoogleSheetsWriter.append()
                                                       │
                                                       ↓
                                                 Google Sheet
                                              (Tab: HotProducts)
                                              (欄位 A:K)
```

### 3.2 Google Sheet 11 個欄位

```
A: collected_at      ISO8601 UTC 時間戳
B: platform          tiktok / threads / vendor
C: market            US / TW / ...
D: product_name      商品名稱
E: product_url       商品連結
F: price             價格（字串）
G: currency          幣別
H: sold_count        原始售出數字串（如 "1.2K sold"）
I: engagement_score  解析後的分數（float）
J: source_url        原始爬取來源 URL
K: raw_signal        原始摘要（限 500 字）
```

### 3.3 已實作的兩個來源

#### `TikTokShopSearchSource`（爬 shop.tiktok.com 公開搜尋頁）
- 使用 httpx + BeautifulSoup
- 三種解析路徑：
  1. `<script type="application/ld+json">` 的 Product / ItemList 結構化資料
  2. `[data-e2e*='product']` selector
  3. `a[href*='/shop/pdp/']` selector
- 用 tenacity 做 3 次重試 + exponential backoff
- 偽造瀏覽器 User-Agent
- 從 URL 推斷市場（`/us/` → US, `/tw/` → TW）

#### `CustomJsonSource`（通用 JSON API 接口）
- 從 `.env` 的 `CUSTOM_JSON_ENDPOINT` 讀取
- 支援自訂單一 auth header（格式 `Name: Value`）
- 接受 array 或 `{ "items": [...] }` 結構
- 自動 mapping：title/name/product_name、url/product_url、price、sales/sold_count 等
- **這是給接資料商 API 用的擴充點**（Apify、Bright Data、Kalodata、FastMoss 等）

---

## 4. 現存問題（Code Review）

### 4.1 嚴重 — 實際資料抓不到 ⚠️⚠️⚠️
TikTok Shop 公開頁面是 **JavaScript 渲染 + Cloudflare anti-bot**，`httpx` 直接 GET 幾乎拿不到產品資料：
- HTML 是空殼
- 容易直接 403 / JS challenge
- `[data-e2e*='product']` selector 隨時會失效
- GitHub Actions 的雲端 IP 早被列黑名單

**結論：dry-run 出來八成是 `[]`**

### 4.2 中等 — Threads 沒實作
README 提到 Threads 但 `sources/` 沒有 Threads 實作。`platform: "threads"` 只是個 label，實際靠 `custom_json` 接外部來源。

### 4.3 中等 — GitHub Actions secret 寫法不安全
`.github/workflows/scheduled.yml` 第 18 行：
```yaml
run: echo "$GOOGLE_SERVICE_ACCOUNT_JSON" > service-account.json
```
- `echo` 對含 `\n` 的 JSON 內容容易在某些 shell 跑掉換行
- 改用 `printf '%s'` 或 base64 解碼較穩
- 另外 line 28 用的是 `sources.example.yml` 而不是 `sources.yml`，需確認意圖

### 4.4 小 — `sources.yml` 跟 `sources.example.yml` 完全相同
等於還沒客製，可以放心直接改 `sources.yml` 做為實際設定。

### 4.5 小 — `engagement_score` 用 `float` 但 sheet 欄位定義是字串型
寫進 sheet 時 `valueInputOption="RAW"`，float 會以數字寫入沒問題，但 mixed types 在 sheet 篩選時要注意。

### 4.6 小 — 沒有 logging
全靠 `print` 跟例外往上拋，排程化後查問題會痛。

### 4.7 小 — 沒有 tests
沒有任何 `tests/` 目錄。

---

## 5. 與 workspace 既有資產的關係

### 5.1 重要：MS_New_BA 已有的相關檔案
這個 workspace `/Users/willielin/MS_New_BA` 已經有類似的管線，可以複用：

| 既有檔案 | 用途 | 可否複用 |
|---|---|---|
| `service_account_key.json` | Google service account 金鑰 | ✅ **可直接複製到新專案** |
| `meta_insights_pipeline.py` | Meta 廣告資料 → Sheet | 參考其結構 |
| `csv_to_sheet_overwrite.py` | CSV 寫入 Sheet 工具 | 可參考 |
| `requirements_meta_pipeline.txt` | Meta 管線依賴 | 參考 |
| `requirements_csv_to_sheet.txt` | CSV-to-Sheet 依賴 | 參考 |
| `run_fb_pipeline.sh` | shell wrapper | 參考 |
| `META_PIPELINE_README.md` | 文件 | 參考 |
| `google_apps_script/` | Apps Script 版本 | 已有的另一條路線 |

### 5.2 整合建議（更新：2026-05-12）
- **Service account 金鑰可共用**：把 `MS_New_BA/service_account_key.json` 複製到 `tiktok_threads_hot_products/service-account.json`，並把目標 Sheet 分享給該 SA email
- ~~未來考慮把兩個專案合併~~ → **不合併**：Meta 已決定放棄，TikTok 維持獨立專案即可

---

## 6. 下一步行動清單

### Phase 0：先驗證骨架（30 分鐘）
- [ ] 建虛擬環境 + 安裝
  ```bash
  cd /Users/willielin/tiktok_threads_hot_products
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -e .
  ```
- [ ] 把 `MS_New_BA/service_account_key.json` 複製成 `tiktok_threads_hot_products/service-account.json`
- [ ] 把目標 Google Sheet 分享給 service account email（Editor 權限）
- [ ] dry-run 看 TikTok 公開頁是否真抓得到
  ```bash
  hot-products run --config config/sources.yml --dry-run
  ```
- [ ] 改一筆假資料，跑非 dry-run，驗證 Sheet 可寫入

### Phase 1：選資料來源路線（這禮拜決定）
比較選項：

| 路線 | 月成本 | 開發成本 | 資料品質 | 合法性 |
|---|---|---|---|---|
| A. Apify TikTok Shop actor | $50–200 USD | 1 天 | ⭐⭐⭐⭐ | ✅ |
| B. TikTok Shop Partner API | 免費 | 需審核（賣家身份） | ⭐⭐⭐⭐⭐ | ✅ 最正式 |
| C. Playwright + 住宅代理 | 代理 $50+ | 1–2 週 | ⭐⭐⭐ | ⚠️ 灰色 |
| D. Kalodata / FastMoss / EchoTik | $30–300 | 0.5 天 | ⭐⭐⭐⭐ | ✅ |
| E. 維持現狀直接跑 | $0 | 0 | ⭐（趨近 0） | — |

**推薦：D（第三方 TikTok Shop 數據商）+ Threads 透過 Apify**

### Phase 2：實作（決定路線後）
- [ ] 把選定的資料商 API 接進 `CustomJsonSource`（或新建 source class）
- [ ] 修 GitHub Actions workflow（用 base64 或 `printf` 寫 secret）
- [ ] 加 logging（替換掉 `print`）
- [ ] 設計「熱門分數」演算法（依銷量、出現頻率、價格、佣金率）
- [ ] 加 unit tests（至少 scoring、dedupe、sheet writer mock）

### Phase 3：上線
- [ ] 初始化 git repo + 推到 GitHub
- [ ] 設定 GitHub Secrets（GOOGLE_SERVICE_ACCOUNT_JSON、GOOGLE_SHEET_ID、CUSTOM_JSON_*）
- [ ] 啟用 GitHub Actions 排程
- [ ] 加錯誤通知（Slack/Email webhook）

---

## 7. 關鍵指令備忘

```bash
# 建置
cd /Users/willielin/tiktok_threads_hot_products
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# 執行 (寫入 sheet)
hot-products run --config config/sources.yml

# 執行 (只看輸出，不寫入)
hot-products run --config config/sources.yml --dry-run

# 一鍵 wrapper
./scripts/run_once.sh

# 本機 cron 範例（每 6 小時）
# 0 */6 * * * cd /Users/willielin/tiktok_threads_hot_products && . .venv/bin/activate && hot-products run --config config/sources.yml >> logs/run.log 2>&1
```

---

## 8. 開放問題 / 待澄清（聚焦 TikTok 後）

1. **TikTok Shop 是要做哪個市場？**
   - 目前 `sources.yml` 只設了 US。
   - 候選：US / TW / SG / MY / ID / VN / TH / PH / UK
   - 不同市場資料商支援程度不同（例如 Kalodata 強在 US/SEA，FastMoss 強在 US/UK）
2. **是要「TikTok Shop 商品」、「TikTok 影片帶貨」、還是「直播帶貨」？**
   - 三個維度資料來源不同，先聚焦哪一個？
3. **抓取頻率？** 每小時 / 每 6 小時 / 每天？（影響 API 成本）
4. **「熱門」的定義？**
   - 純銷量？
   - 銷量 × 影片觸及 × 直播頻率 × 佣金率 × 評分？
   - 短期爆紅（24h 變化率）vs 長期穩定？
5. **預算上限？** 決定能選 D（資料商，月費 $30–300）還是 C（自架 + 代理，月費 $50+）
6. **產出給誰用？** 自己看 / 給選品團隊 / 給 KOL 媒合 / 給老闆？影響欄位設計

---

## 9. 建議的優先順序（聚焦 TikTok 版）

### 立刻可做（不花錢）
1. **Phase 0 驗證骨架**：建 venv、複製 service account、跑 dry-run，確認 Sheet 寫入正常
2. **修現存小 bug**：GitHub Actions 的 `sources.example.yml` 跑錯設定檔、`echo` JSON 不安全

### 短期決策（這禮拜）
3. **確定要做的 TikTok 市場 + 維度**（看上面開放問題 1 + 2）
4. **試 1–2 家資料商試用版**：Kalodata、FastMoss、EchoTik 都可申請 free trial
5. **暫時關掉 TikTok 公開爬蟲**：`sources.yml` 的 `tiktok_shop_search.enabled` 改 false，避免 cron 一直跑空

### 中期實作（1–2 週）
6. 接資料商 API（透過 `CustomJsonSource` 或新建 `TikTokVendorSource`）
7. 加 logging（替換掉 `print`）
8. 設計「熱門分數」演算法（先簡單：依銷量分位數）
9. 加 unit tests（scoring、dedupe、sheet writer mock）

### 上線（2–3 週）
10. 初始化 git repo + 推到 GitHub
11. GitHub Secrets + 啟用 Actions 排程
12. 加錯誤通知（Slack/Email webhook）

### 之後再說
- Threads 資料源
- 跟 MS_New_BA 既有 Meta pipeline 整併（既然已決定不做 Meta，就不整併了）

