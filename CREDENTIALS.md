# Credentials Setup

所有機敏憑證（API keys、tokens、service account）存放在獨立的**私有** repo。
請向專案負責人（Willie Lin）索取存取權限。

---

## 需要哪些憑證

| 變數 | 在哪裡取得 |
|---|---|
| `TIKTOK_APP_ID` | TikTok Developer Portal |
| `TIKTOK_APP_SECRET` | 同上 |
| `TIKTOK_ACCESS_TOKEN` | 執行 `python auth_advertiser.py` |
| `ANTHROPIC_API_KEY` | platform.anthropic.com/settings/keys |
| `GOOGLE_SHEET_ID` | 由專案負責人提供 |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | 由專案負責人提供 service account JSON |

---

## 本機設定步驟

```bash
# 1. 從專案負責人取得 .env 檔案，放到：
tiktok-marketing-api/.env

# 2. 從專案負責人取得 .tokens/ 目錄，放到：
tiktok-marketing-api/.tokens/

# 3. 確認 .env 內 GOOGLE_SERVICE_ACCOUNT_FILE 指向正確路徑
```

詳細說明請聯絡專案負責人。
