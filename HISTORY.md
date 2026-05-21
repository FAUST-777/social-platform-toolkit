# HISTORY

## 2026-05-21 — Slack 通知整合完成

### 完成項目
- 建立 Slack App（GitHub Notify）並設定 Incoming Webhook
- Webhook URL 存入 `private-credentials-repo` 私人 repo（`.env` + README）
- GitHub Actions secret `SLACK_WEBHOOK_URL` 設定完畢
- `weekly_report.yml` 加入成功/失敗雙向 Slack 通知
- 修正 `update_cover_sheet()` NameError（`advertiser_id` 未傳入參數）
- 手動觸發測試通過，Slack 收到 ✅ 成功通知

### 目前自動化流程
每週日 00:00（台灣時間）GitHub Actions 自動執行：
1. 從 TikTok Marketing API 拉最近 7 天廣告數據
2. 寫入 Google Sheet「TikTok廣告成效」（去重）
3. 更新 safe cover 封面頁（最後更新時間、資料區間）
4. 輸出 CSV 到 `reports/` 並 commit 至 GitHub
5. 發送 Slack 通知（成功/失敗）

---

## 2026-05-21 — 安全性修正與 repo 權限調整

### 完成項目
- `social-platform-toolkit` 設為公開（TikTok 專案）
- `line-bot` 設為私人（含硬編碼 token）
- `HISTORY.md` 所有機敏 ID 遮蔽（advertiser ID、App ID、Pixel ID、Sheet URL）
- `CREDENTIALS.md` 移除私人 repo 名稱
- `ad_reports.py` 修正硬編碼 advertiser ID → 改用變數

---

## 2026-05-21 — TK大表重構 + QA Agent 上線

### 完成項目
- Google Sheet tab 順序最終確認（7 個 tab）
- `TikTok廣告成效` 清空重寫，24 欄格式對齊
- KOL成效排名、廣告組排名獨立 tab 建立
- QA Agent（`qa_agent.py`）建立，使用 Claude Opus 4.7
- MKT 分析（`analyze_ads.py`）系統提示強化（寄生社交理論、CTR 標竿研究）
- 去重邏輯修正（廣告ID + 日期），消除 100% 花費重複問題

---

## 2026-05-21 — TikTok APP 審核通過，OAuth 完成

### 完成項目
- TikTok Developer App 審核通過
- Vercel 部署 OAuth callback（advertiser 授權）
- 執行 `auth_advertiser.py` 取得 access token
- advertiser_ids 確認，API 拉資料測試成功（68 筆）
- GitHub Actions `weekly_report.yml` 建立（每週六 16:00 UTC）

---

## 背景說明

專案：**OP實驗型-直播帶貨**
TikTok 頻道：`@17shoptaiwan`
電商平台：mokibuy
TK大表：Google Sheet（含 7 個 tab，記錄廣告成效與 AI 分析）

機敏憑證存放於私人 repo（請向專案負責人 Willie Lin 索取）。
