# social-platform-toolkit

> OrderPally（17LIVE 旗下電商品牌）社群平台數據整合工具集：TikTok 廣告投放、KOL 直播、熱門商品趨勢的多方數據管線

## 🎯 用途

公司業務模式：
- 自家 TikTok 頻道 + KOL 進來開直播帶貨
- 商品賣在其他電商平台（非 TikTok Shop）
- 需要 TikTok 廣告成效 + 直播觀眾數據 + 商品熱度等多維度數據

這個 repo 收錄所有 TikTok 相關的工具與管線：OAuth 認證服務、廣告/直播數據 API pipeline、熱門商品爬蟲實驗。

> 📌 Threads / FB 不在這個 repo（Threads 暫緩 / FB 不做）

## 🗂️ 子專案

### 1. `tiktok-oauth-callback/` — Vercel OAuth 回呼服務
TikTok Marketing API / Business API 申請 App 時要求的 callback endpoint，部署在 Vercel：
- `/api/advertiser-callback` — 廣告主授權回呼
- `/api/account-callback` — TikTok 帳號擁有者授權回呼
- 主頁 `/` — 服務說明頁（讓 TikTok 審核員看的）

部署：直接把 `tiktok-oauth-callback/` 推到 Vercel，自動拿到 HTTPS URL。

### 2. `tiktok-hot-products-pipeline/` — TikTok Shop 熱門商品實驗
Codex 建的 Python pipeline，目標是收集 TikTok Shop 公開搜尋頁的商品資訊寫進 Google Sheet。
- ⚠️ **狀態：實驗中，公開頁爬蟲成功率低**
- 真正可行做法：接資料商 API（Kalodata / FastMoss / EchoTik）或 Apify

## 📊 整體架構

```
┌─────────────────────────────────────────────────────┐
│  TikTok 業務數據                                      │
│                                                      │
│  ┌──────────────┐     ┌──────────────────┐         │
│  │ 公司 TikTok   │ ←─ KOL 進來開直播       │         │
│  │ 頻道 (1個)    │                          │         │
│  └──────┬───────┘                          │         │
│         │                                  │         │
│         ├──→ 付費投放 → Marketing API     │         │
│         │              (廣告成效)           │         │
│         │                                  │         │
│         └──→ 自然觸及 → TikTok Accounts API│         │
│                        (直播觀眾、互動)     │         │
│                                                      │
│  整合到 Google Sheet → Looker Studio                 │
└─────────────────────────────────────────────────────┘

       (此 repo 的 OAuth 服務負責授權拿 token)
```

## 🚧 進度狀態

| 項目 | 狀態 |
|---|---|
| TikTok BC 加入公司廣告帳戶 | ✅ 完成（中途卡 email 一致性問題） |
| TikTok Business Center Admin 權限 | ✅ 完成 |
| TikTok For Developers App 申請 | ⚠️ 一次被駁回，準備重申請 |
| OAuth Callback Service（Vercel） | 📁 程式已備齊，等部署 |
| Marketing API 接入 | 🚧 等 App 過審 |
| TikTok Accounts API 接入 | 🚧 等 App 過審 |
| Scrapling 爬蟲實驗 | 🚧 評估中 |

## 📜 開發歷程

完整的設計決策、踩坑紀錄、API 限制歷程 → 看 [HISTORY.md](./HISTORY.md)

## 🔗 相關專案

- [`marketing-insights-pipeline`](https://github.com/FAUST-777/marketing-insights-pipeline) — Meta（FB）的對應版本
