# TikTok / Threads Hot Products Pipeline

這個專案用來定期收集 TikTok/Threads 上的直播帶貨或社群電商商品訊號，整理後寫入 Google Sheet。

目前架構刻意把「資料來源」做成可插拔，因為 TikTok/Threads 的公開頁面與 API 權限會變動：

- TikTok Shop：建議正式環境使用 TikTok Shop Partner/Open API 或授權資料商。公開搜尋頁解析只適合原型驗證。
- Threads：官方 API 主要支援發文、讀取自己的內容、回覆管理與洞察，不適合作為全站商品熱門榜來源。建議接第三方資料集、社群監測工具或自有授權資料。

## 建置

```bash
cd /Users/willielin/tiktok_threads_hot_products
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
cp config/sources.example.yml config/sources.yml
```

## Google Sheet 設定

1. 到 Google Cloud 建立 Service Account。
2. 啟用 Google Sheets API。
3. 下載 service account JSON，放在專案根目錄，例如 `service-account.json`。
4. 把目標 Google Sheet 分享給 service account email，權限設為 Editor。
5. 在 `.env` 填入：

```bash
GOOGLE_SERVICE_ACCOUNT_FILE=./service-account.json
GOOGLE_SHEET_ID=你的_sheet_id
GOOGLE_SHEET_TAB=HotProducts
```

## 執行

```bash
hot-products run --config config/sources.yml
```

先不寫入 Google Sheet、只看輸出：

```bash
hot-products run --config config/sources.yml --dry-run
```

## 排程

本機 cron 範例：

```cron
0 */6 * * * cd /Users/willielin/tiktok_threads_hot_products && . .venv/bin/activate && hot-products run --config config/sources.yml >> logs/run.log 2>&1
```

GitHub Actions 範例在 `.github/workflows/scheduled.yml`。正式使用時，把 `.env` 內容改成 GitHub Secrets。

## Google Sheet 欄位

| 欄位 | 說明 |
| --- | --- |
| collected_at | 收集時間 |
| platform | tiktok / threads / vendor |
| market | 市場 |
| product_name | 商品名稱 |
| product_url | 商品連結 |
| price | 價格 |
| currency | 幣別 |
| sold_count | 銷量或平台顯示售出數 |
| engagement_score | 互動/熱門程度分數 |
| source_url | 原始資料來源 |
| raw_signal | 原始摘要 |

## 下一步

最實用的正式化路線：

1. 申請 TikTok Shop Partner Center App，接官方商品/店家授權資料。
2. Threads 改接社群監測 API 或合法資料商，而不是直接硬爬公開頁。
3. 依你的市場與品類定義「熱門」分數，例如銷量、直播出現頻率、互動數、價格區間與佣金率。
